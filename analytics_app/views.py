from __future__ import annotations

import uuid

import pandas as pd
import plotly.express as px
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_http_methods

from .constants import (
    BURNOUT_CRITICAL_THRESHOLD,
    LEAVE_HIGH_THRESHOLD,
    LEAVE_LOW_THRESHOLD,
)
from .forms import DatasetUploadForm, IndividualAnalysisForm, MassMonitoringForm
from .models import CsvReport, HRDataset
from .services.assets import AssetNotFoundError, load_assets
from .services.predict import predict_burnout_batch, predict_individual, predict_leave_batch


def _plot_html(fig) -> str:
    fig.update_layout(
        margin=dict(l=10, r=10, t=40, b=10),
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=12),
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


def _df_preview(df: pd.DataFrame, *, limit: int = 10) -> dict:
    head = df.head(limit)
    return {
        "columns": list(head.columns),
        "rows": head.fillna("").values.tolist(),
    }


def _is_hr(user) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name="HR").exists()


def hr_required(view_func):
    return login_required(user_passes_test(_is_hr)(view_func))


def _active_dataset(*, user, kind: str) -> HRDataset | None:
    return (
        HRDataset.objects.filter(user=user, kind=kind, is_active=True)
        .order_by("-created_at")
        .first()
    )


def _read_dataset_csv(dataset: HRDataset) -> pd.DataFrame:
    with dataset.file.open("rb") as f:
        return pd.read_csv(f)


def _upload_and_activate(request, uploaded, name: str, kind: str) -> HRDataset:
    """Сохраняет загруженный файл как новый активный датасет указанного типа."""
    if not name:
        name = uploaded.name
    with transaction.atomic():
        HRDataset.objects.filter(user=request.user, kind=kind, is_active=True).update(
            is_active=False
        )
        return HRDataset.objects.create(
            user=request.user,
            kind=kind,
            name=name,
            file=uploaded,
            is_active=True,
        )


def _latest_report_summary(*, user, kind: str) -> dict | None:
    report = CsvReport.objects.filter(user=user, kind=kind).order_by("-created_at").first()
    if not report:
        return None

    try:
        with report.file.open("rb") as f:
            df = pd.read_csv(f)
    except Exception:
        return {"report": report, "error": "Не удалось прочитать файл отчета."}

    if kind == CsvReport.Kind.LEAVE:
        prob = df.get("Risk_Prob", pd.Series(dtype=float))
        total = max(len(prob), 1)
        high = int((prob > LEAVE_HIGH_THRESHOLD).sum())
        medium = int(((prob <= LEAVE_HIGH_THRESHOLD) & (prob > LEAVE_LOW_THRESHOLD)).sum())
        low = int((prob <= LEAVE_LOW_THRESHOLD).sum())
        out = {
            "high": high,
            "medium": medium,
            "low": low,
            "high_pct": round(high / total * 100),
            "medium_pct": round(medium / total * 100),
            "low_pct": round(low / total * 100),
        }
    else:
        burn = df.get("Burn_Pred", pd.Series(dtype=float))
        out = {
            "critical": int((burn > BURNOUT_CRITICAL_THRESHOLD).sum()),
        }

    return {"report": report, "summary": out}


@csrf_protect
@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            hr_group, _ = Group.objects.get_or_create(name="HR")
            user.groups.add(hr_group)
            login(request, user)
            return redirect("dashboard")
    else:
        form = UserCreationForm()

    return render(request, "registration/register.html", {"form": form})


@hr_required
@require_http_methods(["GET", "POST"])
def datasets(request):
    form = DatasetUploadForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        kind = form.cleaned_data["kind"]
        uploaded = form.cleaned_data["file"]
        name = form.cleaned_data["name"].strip() if form.cleaned_data["name"] else ""
        dataset = _upload_and_activate(request, uploaded, name, kind)
        messages.success(request, f"Датасет '{dataset.name}' загружен и выбран активным.")
        return redirect("datasets")

    leave_sets = HRDataset.objects.filter(user=request.user, kind=HRDataset.Kind.LEAVE).order_by(
        "-created_at"
    )
    burnout_sets = HRDataset.objects.filter(
        user=request.user, kind=HRDataset.Kind.BURNOUT
    ).order_by("-created_at")

    return render(
        request,
        "analytics_app/datasets.html",
        {
            "form": form,
            "leave_sets": leave_sets,
            "burnout_sets": burnout_sets,
        },
    )


@hr_required
@require_http_methods(["POST"])
def dataset_set_active(request, dataset_id: uuid.UUID):
    dataset = get_object_or_404(HRDataset, id=dataset_id, user=request.user)
    with transaction.atomic():
        HRDataset.objects.filter(user=request.user, kind=dataset.kind, is_active=True).update(
            is_active=False
        )
        dataset.is_active = True
        dataset.save(update_fields=["is_active"])
    messages.success(request, f"Активный датасет выбран: {dataset.name}")
    return redirect("datasets")


@hr_required
@require_http_methods(["POST"])
def dataset_delete(request, dataset_id: uuid.UUID):
    dataset = get_object_or_404(HRDataset, id=dataset_id, user=request.user)
    was_active = dataset.is_active
    kind = dataset.kind
    dataset.delete()

    if was_active:
        latest = (
            HRDataset.objects.filter(user=request.user, kind=kind).order_by("-created_at").first()
        )
        if latest:
            latest.is_active = True
            latest.save(update_fields=["is_active"])

    messages.info(request, "Датасет удален.")
    return redirect("datasets")


@hr_required
@require_GET
def dashboard(request):
    dataset = _active_dataset(user=request.user, kind=HRDataset.Kind.LEAVE)
    df = None
    if dataset is not None:
        try:
            df = _read_dataset_csv(dataset)
        except Exception:
            messages.warning(request, "Не удалось прочитать активный датасет Leave.")

    metrics = {
        "employees": None,
        "avg_age": None,
        "avg_experience": None,
        "turnover_pct": None,
    }
    charts = {}

    if df is not None:
        metrics["employees"] = int(len(df))

        if "Age" in df.columns:
            metrics["avg_age"] = round(float(df["Age"].mean()), 1)

        if "ExperienceInCurrentDomain" in df.columns:
            metrics["avg_experience"] = round(float(df["ExperienceInCurrentDomain"].mean()), 1)

        if "LeaveOrNot" in df.columns:
            metrics["turnover_pct"] = round(float(df["LeaveOrNot"].mean() * 100), 1)

        # График 1: Распределение по офисам
        if "City" in df.columns:
            cc = df["City"].value_counts().reset_index()
            cc.columns = ["Офис", "Сотрудников"]
            fig_city = px.bar(
                cc, x="Офис", y="Сотрудников",
                title="Сотрудники по офисам",
                color_discrete_sequence=["#6366F1"],
                text="Сотрудников",
            )
            fig_city.update_traces(textposition="auto")
            fig_city.update_yaxes(title_text="")
            charts["geo"] = _plot_html(fig_city)

        # График 2: Структура компенсаций (с понятными подписями)
        if "PaymentTier" in df.columns:
            tier_label = {1: "Tier 1 — высокий", 2: "Tier 2 — средний", 3: "Tier 3 — низкий"}
            tier_color = {
                "Tier 1 — высокий": "#16A34A",
                "Tier 2 — средний": "#D97706",
                "Tier 3 — низкий": "#DC2626",
            }
            df_t = df.copy()
            df_t["Уровень"] = df_t["PaymentTier"].map(tier_label)
            tc = df_t["Уровень"].value_counts().reset_index()
            tc.columns = ["Уровень", "Кол-во"]
            # Фиксируем порядок: высокий → средний → низкий
            tc["_order"] = tc["Уровень"].map(
                {"Tier 1 — высокий": 0, "Tier 2 — средний": 1, "Tier 3 — низкий": 2}
            )
            tc = tc.sort_values("_order").drop(columns="_order")
            fig_tier = px.bar(
                tc, x="Уровень", y="Кол-во",
                title="Структура компенсаций",
                color="Уровень",
                color_discrete_map=tier_color,
                text="Кол-во",
            )
            fig_tier.update_traces(textposition="auto")
            fig_tier.update_layout(showlegend=False)
            fig_tier.update_yaxes(title_text="")
            charts["tiers"] = _plot_html(fig_tier)

        # График 3: Гендерный баланс
        if "Gender" in df.columns:
            gc = df["Gender"].value_counts().reset_index()
            gc.columns = ["Пол", "Кол-во"]
            charts["gender"] = _plot_html(
                px.pie(
                    gc, names="Пол", values="Кол-во", hole=0.5,
                    title="Гендерный баланс",
                    color_discrete_sequence=["#3B82F6", "#F472B6"],
                )
            )

        # График 4: Динамика найма по годам
        if "JoiningYear" in df.columns:
            yc = df["JoiningYear"].value_counts().sort_index().reset_index()
            yc.columns = ["Год", "Нанято"]
            fig_hire = px.bar(
                yc, x="Год", y="Нанято",
                title="Динамика найма по годам",
                color_discrete_sequence=["#8B5CF6"],
                text="Нанято",
            )
            fig_hire.update_traces(textposition="auto")
            fig_hire.update_xaxes(type="category")
            fig_hire.update_yaxes(title_text="")
            charts["hiring"] = _plot_html(fig_hire)

        # График 5: Распределение опыта
        if "ExperienceInCurrentDomain" in df.columns:
            fig_exp = px.histogram(
                df, x="ExperienceInCurrentDomain",
                title="Профиль опыта сотрудников",
                color_discrete_sequence=["#10B981"],
                labels={"ExperienceInCurrentDomain": "Лет опыта в домене", "count": "Кол-во"},
            )
            fig_exp.update_traces(marker_line_width=0.5, marker_line_color="white")
            fig_exp.update_xaxes(dtick=1)
            fig_exp.update_yaxes(title_text="Кол-во")
            charts["experience"] = _plot_html(fig_exp)

    last_leave = _latest_report_summary(user=request.user, kind=CsvReport.Kind.LEAVE)
    last_burn = _latest_report_summary(user=request.user, kind=CsvReport.Kind.BURNOUT)

    return render(
        request,
        "analytics_app/dashboard.html",
        {
            "metrics": metrics,
            "charts": charts,
            "active_leave_dataset": dataset,
            "last_leave": last_leave,
            "last_burn": last_burn,
        },
    )


@hr_required
@require_http_methods(["GET", "POST"])
def individual_analysis(request):
    try:
        assets = load_assets()
    except (AssetNotFoundError, Exception) as exc:
        return render(request, "analytics_app/error.html", {"error": str(exc)})

    result = None
    report_ready = False

    if request.method == "POST":
        form = IndividualAnalysisForm(request.POST)
        if form.is_valid():
            cleaned = form.cleaned_data
            cleaned["payment_tier"] = int(cleaned["payment_tier"])
            result = predict_individual(
                model_burnout=assets.model_burnout,
                model_leave=assets.model_leave,
                inputs=cleaned,
            )
            report_text = _build_report_text(cleaned, result)
            # Сохраняем отчёт в файл, в сессии храним только путь
            report_filename = f"Report_Employee_{timezone.now().strftime('%Y%m%d_%H%M%S')}.txt"
            report_path = f"reports/individual/{report_filename}"
            default_storage.save(report_path, ContentFile(report_text.encode("utf-8")))
            request.session["last_report_path"] = report_path
            request.session["last_report_filename"] = report_filename
            report_ready = True
    else:
        form = IndividualAnalysisForm()

    burnout_pct = round(result.burnout_score * 100) if result else None
    leave_pct = round(result.leave_proba * 100) if result else None

    return render(
        request,
        "analytics_app/individual.html",
        {
            "form": form,
            "result": result,
            "report_ready": report_ready,
            "burnout_pct": burnout_pct,
            "leave_pct": leave_pct,
        },
    )


def _build_report_text(inputs: dict, result) -> str:
    recs = result.recommendations
    rec_lines = "\n".join([f"- {r}" for r in recs]) if recs else "Риски минимальны, меры не требуются."
    return (
        "# ОТЧЕТ ПО АНАЛИЗУ РИСКОВ ПЕРСОНАЛА\n\n"
        f"Дата анализа: {timezone.now().strftime('%d.%m.%Y')}\n"
        f"Профиль сотрудника: {inputs['gender']}, {inputs['age']} лет, {inputs['education']}\n"
        f"Должность: Уровень {inputs['designation']}, Стаж {inputs['days_employed']} дн.\n\n"
        "Результаты прогнозирования:\n"
        f"- Вероятность увольнения: {round(result.leave_proba * 100, 1)}%\n"
        f"- Индекс ментального выгорания: {round(result.burnout_score, 2)} / 1.0\n\n"
        "Рекомендованные меры:\n"
        f"{rec_lines}\n\n"
        "Отчет сформирован интеллектуальной системой HR-аналитики.\n"
    )


@hr_required
@require_GET
def download_report(request):
    report_path = request.session.get("last_report_path")
    filename = request.session.get("last_report_filename") or "Report.txt"
    if not report_path or not default_storage.exists(report_path):
        return redirect("individual")
    return FileResponse(
        default_storage.open(report_path, "rb"),
        as_attachment=True,
        filename=filename,
        content_type="text/plain; charset=utf-8",
    )


def _write_csv_report(
    request, df: pd.DataFrame, kind: CsvReport.Kind, dataset: HRDataset | None
) -> uuid.UUID:
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    report = CsvReport.objects.create(
        user=request.user,
        dataset=dataset,
        kind=kind,
    )
    report.file.save(
        f"{kind}_Report_{report.id}.csv",
        ContentFile(csv_bytes),
        save=True,
    )
    return report.id


def _prepare_leave_context(request, df: pd.DataFrame, dataset: HRDataset | None) -> dict:
    report_id = _write_csv_report(request, df, CsvReport.Kind.LEAVE, dataset)
    pie = px.pie(
        df,
        names="Cat",
        hole=0.4,
        color="Cat",
        color_discrete_map={"Высокий": "#FF4B4B", "Средний": "#FFA500", "Низкий": "#008000"},
        title="Категории риска увольнения",
    )
    top = df[df["Risk_Prob"] > LEAVE_HIGH_THRESHOLD].sort_values(
        by="Risk_Prob", ascending=False
    )
    return {
        "report_id": report_id,
        "chart": _plot_html(pie),
        "top_table": _df_preview(top, limit=10),
    }


def _prepare_burnout_context(request, df: pd.DataFrame, dataset: HRDataset | None) -> dict:
    report_id = _write_csv_report(request, df, CsvReport.Kind.BURNOUT, dataset)
    hist = px.histogram(
        df,
        x="Burn_Pred",
        color_discrete_sequence=["#FF4B4B"],
        title="Распределение выгорания",
    )
    top = df[df["Burn_Pred"] > BURNOUT_CRITICAL_THRESHOLD].sort_values(
        by="Burn_Pred", ascending=False
    )
    return {
        "report_id": report_id,
        "chart": _plot_html(hist),
        "top_table": _df_preview(top, limit=10),
    }


@hr_required
@require_http_methods(["GET", "POST"])
def mass_monitoring(request):
    try:
        assets = load_assets()
    except (AssetNotFoundError, Exception) as exc:
        return render(request, "analytics_app/error.html", {"error": str(exc)})

    context: dict = {
        "form": MassMonitoringForm(),
        "leave": None,
        "burnout": None,
        "importance": None,
    }

    active_leave = _active_dataset(user=request.user, kind=HRDataset.Kind.LEAVE)
    active_burn = _active_dataset(user=request.user, kind=HRDataset.Kind.BURNOUT)
    context["active_leave_dataset"] = active_leave
    context["active_burnout_dataset"] = active_burn

    if request.method == "POST":
        form = MassMonitoringForm(request.POST, request.FILES)
        if form.is_valid():
            action = request.POST.get("action") or ""
            uploaded = form.cleaned_data.get("file")
            dataset_name = (form.cleaned_data.get("dataset_name") or "").strip()

            try:
                dataset_for_run = None

                if action == "leave":
                    if uploaded:
                        dataset_for_run = _upload_and_activate(
                            request, uploaded, dataset_name, HRDataset.Kind.LEAVE
                        )
                        active_leave = dataset_for_run
                    else:
                        dataset_for_run = active_leave

                    if not dataset_for_run:
                        raise ValueError(
                            "Нет активного датасета Leave. Загрузите CSV в разделе 'Датасеты'."
                        )

                    df_src = _read_dataset_csv(dataset_for_run)
                    leave_df = predict_leave_batch(model_leave=assets.model_leave, df=df_src)
                    context["leave"] = _prepare_leave_context(request, leave_df, dataset_for_run)

                elif action == "burnout":
                    if uploaded:
                        dataset_for_run = _upload_and_activate(
                            request, uploaded, dataset_name, HRDataset.Kind.BURNOUT
                        )
                        active_burn = dataset_for_run
                    else:
                        dataset_for_run = active_burn

                    if not dataset_for_run:
                        raise ValueError(
                            "Нет активного датасета Burnout. Загрузите CSV в разделе 'Датасеты'."
                        )

                    df_src = _read_dataset_csv(dataset_for_run)
                    burn_df = predict_burnout_batch(
                        model_burnout=assets.model_burnout, df=df_src
                    )
                    context["burnout"] = _prepare_burnout_context(
                        request, burn_df, dataset_for_run
                    )

                context["active_leave_dataset"] = active_leave
                context["active_burnout_dataset"] = active_burn

            except Exception as exc:
                context["error"] = f"Ошибка обработки CSV: {exc}"

        context["form"] = form

    context["importance"] = _importance_charts(assets)
    return render(request, "analytics_app/monitoring.html", context)


def _importance_charts(assets) -> dict:
    out: dict[str, str] = {}

    try:
        l_feats = [
            "Education",
            "JoiningYear",
            "City",
            "PaymentTier",
            "Age",
            "Gender",
            "EverBenched",
            "ExperienceInCurrentDomain",
        ]
        importances = getattr(assets.model_leave, "feature_importances_", None)
        if importances is not None:
            imp_df = pd.DataFrame({"Фактор": l_feats, "Вес": importances}).sort_values(by="Вес")
            out["leave"] = _plot_html(
                px.bar(
                    imp_df,
                    x="Вес",
                    y="Фактор",
                    orientation="h",
                    title="Что влияет на увольнение",
                    color_discrete_sequence=["#31333F"],
                )
            )
    except Exception:
        out["leave_error"] = "Не удалось построить график важности для увольнений."

    try:
        b_feats = [
            "Gender",
            "Company Type",
            "WFH Setup Available",
            "Designation",
            "Resource Allocation",
            "Mental Fatigue Score",
            "Days_Employed",
        ]
        importances = assets.model_burnout.get_feature_importance()
        imp_df = pd.DataFrame({"Фактор": b_feats, "Вес": importances}).sort_values(by="Вес")
        out["burnout"] = _plot_html(
            px.bar(
                imp_df,
                x="Вес",
                y="Фактор",
                orientation="h",
                title="Что влияет на выгорание",
                color_discrete_sequence=["#FF4B4B"],
            )
        )
    except Exception:
        out["burnout_error"] = "Не удалось построить график важности для выгорания."

    return out


@hr_required
@require_GET
def download_csv_report(request, report_id: uuid.UUID):
    report = get_object_or_404(CsvReport, id=report_id, user=request.user)
    return FileResponse(
        report.file.open("rb"),
        as_attachment=True,
        filename=report.file.name.split("/")[-1],
        content_type="text/csv; charset=utf-8",
    )
