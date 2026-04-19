from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class IndividualResult:
    burnout_score: float
    leave_proba: float
    recommendations: list[str]


def _safe_float(value) -> float:
    try:
        return float(value)
    except Exception:
        return float("nan")


def predict_individual(*, model_burnout, model_leave, inputs: dict) -> IndividualResult:
    b_input = pd.DataFrame(
        [
            [
                0 if inputs["gender"] == "Female" else 1,
                1 if inputs["company_type"] == "Service" else 0,
                0 if inputs["wfh"] == "No" else 1,
                inputs["designation"],
                inputs["resource_allocation"],
                inputs["mental_fatigue"],
                inputs["days_employed"],
            ]
        ],
        columns=[
            "Gender",
            "Company Type",
            "WFH Setup Available",
            "Designation",
            "Resource Allocation",
            "Mental Fatigue Score",
            "Days_Employed",
        ],
    )
    burnout_score = _safe_float(model_burnout.predict(b_input)[0])

    l_vals = [
        {"Bachelors": 0, "Masters": 1, "PHD": 2}[inputs["education"]],
        inputs["joining_year"],
        {"Bangalore": 0, "Pune": 1, "New Delhi": 2}[inputs["city"]],
        inputs["payment_tier"],
        inputs["age"],
        (1 if inputs["gender"] == "Male" else 0),
        (1 if inputs["ever_benched"] == "Yes" else 0),
        inputs["experience_years"],
    ]
    l_input = pd.DataFrame(
        [l_vals],
        columns=[
            "Education",
            "JoiningYear",
            "City",
            "PaymentTier",
            "Age",
            "Gender",
            "EverBenched",
            "ExperienceInCurrentDomain",
        ],
    )
    leave_proba = _safe_float(model_leave.predict_proba(l_input)[0][1])

    recommendations: list[str] = []

    if leave_proba > 0.8:
        recommendations.append(
            "🔴 Критический риск ухода: нужна индивидуальная встреча в течение 24 часов"
        )
    elif leave_proba > 0.5:
        recommendations.append("🟡 Умеренный риск ухода: провести интервью и пересмотреть KPI")
    elif leave_proba > 0.3:
        recommendations.append("🟢 Низкий риск: стандартный мониторинг, плановый опрос")

    if burnout_score > 0.7:
        recommendations.append(
            "Высокое выгорание: нужен отпуск/смена задач, риск критических ошибок"
        )
    elif burnout_score > 0.4:
        recommendations.append("Начало деструкции: проверить Work‑Life баланс")

    if inputs["payment_tier"] == 3 and leave_proba > 0.4:
        recommendations.append(
            "Зарплатный фактор: низкий уровень оплаты (3), проверьте соответствие рынку"
        )

    if inputs["experience_years"] < 2 and leave_proba > 0.6:
        recommendations.append("Адаптация: может не хватать менторской поддержки")

    if inputs["ever_benched"] == "Yes":
        recommendations.append("Фактор простоя: Bench снижает лояльность, вовлеките в проект")

    if inputs["wfh"] == "No" and burnout_score > 0.5:
        recommendations.append("Гибкость: рассмотрите гибридный график")

    return IndividualResult(
        burnout_score=burnout_score,
        leave_proba=leave_proba,
        recommendations=recommendations,
    )


def predict_leave_batch(*, model_leave, df: pd.DataFrame) -> pd.DataFrame:
    df_work = df.copy()
    df_work["Education"] = df_work["Education"].map({"Bachelors": 0, "Masters": 1, "PHD": 2})
    df_work["City"] = df_work["City"].map({"Bangalore": 0, "Pune": 1, "New Delhi": 2})
    df_work["Gender"] = df_work["Gender"].map({"Female": 0, "Male": 1})
    df_work["EverBenched"] = df_work["EverBenched"].map({"No": 0, "Yes": 1})

    feats = [
        "Education",
        "JoiningYear",
        "City",
        "PaymentTier",
        "Age",
        "Gender",
        "EverBenched",
        "ExperienceInCurrentDomain",
    ]
    out = df.copy()
    out["Risk_Prob"] = model_leave.predict_proba(df_work[feats])[:, 1]
    out["Cat"] = out["Risk_Prob"].apply(
        lambda x: "Высокий" if x > 0.7 else ("Средний" if x > 0.3 else "Низкий")
    )
    return out


def predict_burnout_batch(*, model_burnout, df: pd.DataFrame) -> pd.DataFrame:
    df_work = df.copy()
    df_work["Date of Joining"] = pd.to_datetime(df_work["Date of Joining"])
    df_work["Days_Employed"] = (df_work["Date of Joining"].max() - df_work["Date of Joining"]).dt.days
    df_work = df_work.fillna(df_work.median(numeric_only=True))

    b_feats = [
        "Gender",
        "Company Type",
        "WFH Setup Available",
        "Designation",
        "Resource Allocation",
        "Mental Fatigue Score",
        "Days_Employed",
    ]
    out = df.copy()
    out["Burn_Pred"] = model_burnout.predict(df_work[b_feats])
    return out

