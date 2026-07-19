"""
ml_dataset_gene_final.csv 의 타겟 컬럼(final_call) 클래스 불균형을
SMOTE로 오버샘플링해서 GCP AutoML에 넣기 좋은 형태로 만드는 스크립트.

원본 클래스 분포 (final_call 기준):
    likely to work : 1564  <- 가장 많은 클래스 (majority)
    likely to fail : 1357
    uncertain      :   76

*** 중요: 데이터 증강(SMOTE)은 train에만 적용해야 한다 ***
    validation/test에 합성 샘플이 섞이면
    1) 원본 샘플과 그로부터 만들어진 합성 샘플이 서로 다른 split(train/test)에
       나뉘어 들어갈 수 있고 (사실상 "정답이 살짝 다른 복제본"이 train과 test에
       동시에 존재하는 셈이라 데이터 누수, data leakage 발생)
    2) validation/test 성능이 실제보다 좋게 나와서 모델 성능을 과대평가하게 됨

    그래서 이 스크립트는
    1) 먼저 원본 데이터를 train(80%) / validation(10%) / test(10%)로
       (각 split 안에서 final_call 비율이 유지되도록 stratify) 나누고
    2) SMOTE는 train에만 적용해서 부풀리고, validation/test는 원본 그대로 둔 뒤
    3) "data_split" 컬럼(TRAIN/VALIDATION/TEST)을 추가해 하나의 CSV로 합쳐서 저장한다.

    GCP AutoML(Vertex AI)에 업로드할 때는 이 data_split 컬럼을
    "Manual"(수동) 데이터 분할 컬럼으로 지정하면, AutoML이 자체적으로
    다시 랜덤 split을 하지 않고 이 스크립트가 만든 분할을 그대로 사용한다.
    (Vertex AI 콘솔의 데이터 분할 옵션에서 요구하는 정확한 컬럼값 표기는
    버전에 따라 TRAIN/VALIDATE/TEST 등으로 다를 수 있으니, 실제 업로드 전에
    콘솔 UI에서 한 번 확인하는 걸 권장한다.)

실행 전 필요한 패키지: pandas, scikit-learn, imbalanced-learn
    pip install pandas scikit-learn imbalanced-learn
"""

import re

import pandas as pd
from sklearn.model_selection import train_test_split
from imblearn.over_sampling import SMOTE

# -----------------------------------------------------------------
# 설정값 (경로/컬럼명/비율 등을 한 곳에 모아둠 - 나중에 바꾸기 쉽게)
# -----------------------------------------------------------------
INPUT_CSV = "ml_dataset_gene_final.csv"          # 원본 데이터
OUTPUT_CSV = "ml_dataset_gene_final_smote.csv"    # split + SMOTE 적용 후 저장할 파일
TARGET_COL = "final_call"                          # 오버샘플링 기준이 되는 타겟(라벨) 컬럼
CATEGORY_COL = "antibiotic"                         # 항생제 이름 컬럼 (문자열, 3종류: ciprofloxacin/gentamicin/meropenem)
SPLIT_COL = "data_split"                            # AutoML에 넘길 수동 split 표시 컬럼 (TRAIN/VALIDATION/TEST)
RANDOM_STATE = 42                                   # 재현 가능하도록 랜덤 시드 고정

VAL_RATIO = 0.10   # 전체 대비 validation 비율
TEST_RATIO = 0.10  # 전체 대비 test 비율
# 나머지 (1 - VAL_RATIO - TEST_RATIO) = 0.80 이 train 비율


def sanitize_column_name(name: str) -> str:
    """유전자 컬럼명(예: "aac(6')-Ib-cr")에 들어있는 괄호/따옴표/하이픈 등은
    BigQuery/Vertex AI가 컬럼명으로 허용하지 않는다 (영문자/숫자/밑줄만 허용).
    허용되지 않는 문자를 전부 '_'로 바꾸고, 숫자로 시작하면 앞에 '_'를 붙인다.
    (398개 유전자 컬럼 전체를 검사해봤을 때 이 규칙으로 바꿔도 중복은 발생하지 않음)
    """
    sanitized = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if re.match(r"^[0-9]", sanitized):
        sanitized = "_" + sanitized
    return sanitized


def smote_oversample(X: pd.DataFrame, y: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
    """train 데이터에만 SMOTE를 적용해서 소수 클래스를 majority 클래스 개수까지 채운다.

    SMOTE는 숫자형 입력만 받기 때문에 문자열인 antibiotic 컬럼을 원-핫 인코딩했다가,
    합성 샘플 생성 후 다시 원래 형태(0/1 정수, 단일 카테고리 문자열)로 복원한다.
    """
    # antibiotic(문자열) -> antibiotic_ciprofloxacin, antibiotic_gentamicin, antibiotic_meropenem
    # 같은 0/1 더미 컬럼들로 변환. 나머지 유전자 컬럼들은 그대로 둔다.
    X_encoded = pd.get_dummies(X, columns=[CATEGORY_COL])
    dummy_cols = [c for c in X_encoded.columns if c.startswith(f"{CATEGORY_COL}_")]

    # sampling_strategy="not majority": 가장 많은 클래스(likely to work)는 그대로 두고,
    # 나머지 클래스들만 majority 클래스 개수에 맞춰 합성 샘플로 채운다.
    # k_neighbors=5 (기본값): 이웃 5개 사이를 보간해서 새 샘플을 만듦
    # -> train 안에서 uncertain 클래스가 너무 적으면(<=5) 에러가 나므로
    #    실제 개수를 보고 k_neighbors를 자동으로 낮춘다.
    min_class_count = y.value_counts().min()
    k_neighbors = min(5, max(1, min_class_count - 1))

    smote = SMOTE(sampling_strategy="not majority", random_state=RANDOM_STATE, k_neighbors=k_neighbors)
    X_resampled, y_resampled = smote.fit_resample(X_encoded, y)

    # SMOTE는 두 샘플 "사이"를 보간해서 새 데이터를 만들기 때문에, 원래 0/1
    # 이진값이었던 유전자 컬럼들과 원-핫 antibiotic 컬럼들이 합성 샘플에서는
    # 0.37, 0.82 같은 소수점 값으로 나올 수 있다. 원본 데이터의 의미(있음/없음,
    # 단일 카테고리)를 유지하기 위해 다시 0/1과 문자열 카테고리로 되돌린다.

    # 유전자 컬럼(이진 0/1) 복원: 0.5를 기준으로 반올림
    gene_cols = [c for c in X_resampled.columns if c not in dummy_cols]
    X_resampled[gene_cols] = X_resampled[gene_cols].round().clip(0, 1).astype(int)

    # antibiotic 원-핫 컬럼 복원: 세 더미 컬럼 중 값이 가장 큰 것을 골라
    # 다시 원래처럼 "ciprofloxacin" / "gentamicin" / "meropenem" 문자열 하나로 합친다
    antibiotic_series = X_resampled[dummy_cols].idxmax(axis=1).str.replace(f"{CATEGORY_COL}_", "", regex=False)
    X_resampled = X_resampled.drop(columns=dummy_cols).copy()
    X_resampled.insert(0, CATEGORY_COL, antibiotic_series)

    return X_resampled, y_resampled


def main() -> None:
    # ---------------------------------------------------------
    # 1) 데이터 불러오기
    # ---------------------------------------------------------
    df = pd.read_csv(INPUT_CSV)

    # Vertex AI(AutoML Tabular) 학습 시 컬럼명으로 못 쓰는 특수문자가 유전자
    # 컬럼명에 많이 섞여 있어서(예: "aac(6')-Ib-cr") 미리 안전한 이름으로 정리한다.
    # TARGET_COL/CATEGORY_COL은 특수문자가 없어 sanitize해도 그대로 유지된다.
    df = df.rename(columns=sanitize_column_name)

    before_counts = df[TARGET_COL].value_counts()

    # ---------------------------------------------------------
    # 2) train / validation / test 로 먼저 분할 (SMOTE 적용 "전"!)
    #    stratify=df[TARGET_COL] 로 각 split 안에서도 원본과 동일한
    #    클래스 비율(불균형 포함)이 유지되도록 한다.
    #    -> validation/test는 실제 세상의 불균형 분포를 그대로 반영해야
    #       모델 성능을 왜곡 없이 평가할 수 있기 때문에 일부러 그대로 둔다.
    # ---------------------------------------------------------
    train_val_df, test_df = train_test_split(
        df,
        test_size=TEST_RATIO,
        stratify=df[TARGET_COL],
        random_state=RANDOM_STATE,
    )
    # train_val_df 안에서 다시 validation을 떼어낸다.
    # (전체 대비 VAL_RATIO가 되도록 비율을 재계산)
    val_ratio_within_train_val = VAL_RATIO / (1 - TEST_RATIO)
    train_df, val_df = train_test_split(
        train_val_df,
        test_size=val_ratio_within_train_val,
        stratify=train_val_df[TARGET_COL],
        random_state=RANDOM_STATE,
    )

    # ---------------------------------------------------------
    # 3) SMOTE는 train에만 적용
    # ---------------------------------------------------------
    y_train = train_df[TARGET_COL]
    X_train = train_df.drop(columns=[TARGET_COL])
    X_train_resampled, y_train_resampled = smote_oversample(X_train, y_train)

    # Vertex AI의 manual(predefined) split 컬럼 값은 실제 런타임 검증 기준
    # "TRAIN" / "VALIDATE" / "TEST" (대문자, VALIDATION 아님) 여야 한다.
    # (공식 문서에는 소문자 training/validation/test로 나와 있지만, 실제
    # trainingPipelines API는 이 값을 거부한다 - 잘못된 값이면
    # "Split key should be one of [TRAIN, VALIDATE, TEST, UNASSIGNED]" 에러로 실패함)
    train_resampled_df = X_train_resampled.copy()
    train_resampled_df.insert(1, TARGET_COL, y_train_resampled.values)
    train_resampled_df[SPLIT_COL] = "TRAIN"

    # validation/test는 원본 그대로 (오버샘플링하지 않음), split 표시만 추가
    val_df = val_df.copy()
    val_df[SPLIT_COL] = "VALIDATE"
    test_df = test_df.copy()
    test_df[SPLIT_COL] = "TEST"

    # ---------------------------------------------------------
    # 4) 세 조각을 다시 하나의 CSV로 합치기
    #    컬럼 순서: 원본 컬럼들 + data_split
    # ---------------------------------------------------------
    result = pd.concat([train_resampled_df, val_df, test_df], ignore_index=True)
    result = result[list(df.columns) + [SPLIT_COL]]

    result.to_csv(OUTPUT_CSV, index=False)

    # ---------------------------------------------------------
    # 5) 결과 리포트
    # ---------------------------------------------------------
    print(f"입력 파일: {INPUT_CSV}")
    print(f"출력 파일: {OUTPUT_CSV}\n")

    print("=== split별 원본 행 수 (SMOTE 적용 전, train/val/test 분할 직후) ===")
    print(f"  train      : {len(train_df):>5}개")
    print(f"  validation : {len(val_df):>5}개")
    print(f"  test       : {len(test_df):>5}개")

    print("\n=== train 내부 final_call 클래스 분포 (SMOTE 적용 전 -> 후) ===")
    train_before = y_train.value_counts()
    train_after = train_resampled_df[TARGET_COL].value_counts()
    for label in before_counts.index:
        b = int(train_before.get(label, 0))
        a = int(train_after.get(label, 0))
        print(f"  {label:<15}: {b:>5}개 -> {a:>5}개  (+{a - b})")

    print("\n=== validation / test 클래스 분포 (오버샘플링 없이 원본 비율 유지) ===")
    for label in before_counts.index:
        v = int(val_df[TARGET_COL].value_counts().get(label, 0))
        t = int(test_df[TARGET_COL].value_counts().get(label, 0))
        print(f"  {label:<15}: val {v:>4}개 / test {t:>4}개")

    print(f"\n전체 행 수: {len(df)}개 (원본) -> {len(result)}개 (train만 오버샘플링 후 합산)")


if __name__ == "__main__":
    main()
