import pandas as pd
import numbers

ROW_OFFSET = 2


def _to_number(val):
    if isinstance(val, bool):
        return None
    if isinstance(val, numbers.Number):
        return val
    if isinstance(val, str):
        try:
            return float(val.strip().replace(",", "."))
        except ValueError:
            return None
    return None


# Find empty cells
def find_empty_or_whitespace_cells(df: pd.DataFrame) -> list:
    mask_nan = df.isna()

    mask_space = df.map(lambda x: isinstance(x, str) and x.strip() == "")

    mask_total = mask_nan | mask_space

    stacked = mask_total.stack()
    invalid_coords = stacked[stacked].index

    results = []

    for row_idx, col_name in invalid_coords:
        val = df.at[row_idx, col_name]

        issue_type = "NaN/None" if pd.isna(val) else "Whitespace-only"

        issue = {
            "type": "missing value",
            "issue_type": issue_type,
            "row": row_idx + ROW_OFFSET,
            "column": col_name,
            "value": val
        }
        results.append(issue)
    return results


# find duplicated rows
def find_duplicated_rows(df) -> list:
    duplicated_mask = df.duplicated(keep='first')
    duplicated_indexes = duplicated_mask[duplicated_mask].index

    results = []

    for row_idx in duplicated_indexes:
        issue = {
            "type": "duplicated row",
            "issue_type": "duplicated row",
            "row": row_idx + ROW_OFFSET,
            "column": None,
            "value": None
        }
        results.append(issue)
    return results


# find duplicated values on the columns
def find_duplicated_values(df, column_name) -> list:
    results = []

    if column_name not in df.columns:
        return results

    duplicated_mask = df[column_name].duplicated(keep='first') & df[column_name].notna()
    duplicated_indexes = duplicated_mask[duplicated_mask].index

    for row_idx in duplicated_indexes:
        issue = {
            "type": "duplicated value",
            "issue_type": "duplicated value",
            "row": row_idx + ROW_OFFSET,
            "column": column_name,
            "value": df.at[row_idx, column_name]
        }
        results.append(issue)
    return results


# check column's data type
def validate_dataframe_types(df: pd.DataFrame, column_types_config: dict) -> list:
    results = []

    for col_name, expected_type_str in column_types_config.items():
        if col_name not in df.columns:
            continue

        if expected_type_str not in ("Number", "Text", "Date"):
            results.append({
                "type": "Unknown type config",
                "issue_type": "Expected number, text or date",
                "row": None,
                "column": col_name,
                "value": expected_type_str
            })
            continue

        col = df[col_name]
        filled = col.notna()
        is_str = col.map(lambda v: isinstance(v, str))

        if expected_type_str == "Number":
            cleaned = col.astype(str).str.strip().str.replace(",", ".", regex=False)
            ok = pd.to_numeric(cleaned, errors="coerce").notna()

        elif expected_type_str == "Date":
            is_ts = col.map(lambda v: isinstance(v, pd.Timestamp))
            parsed = pd.to_datetime(col.where(is_str), format="%Y-%m-%d", errors="coerce")
            ok = is_ts | parsed.notna()

            # строки не в формате ГГГГ-ММ-ДД пробуем разобрать мягче, их обычно мало
            retry = is_str & ~ok
            if retry.any():
                second = pd.to_datetime(col[retry], format="mixed", errors="coerce")
                ok = ok.copy()
                ok.loc[retry] = second.notna()

        else:  # Text
            ok = is_str

        bad = filled & ~ok
        for row_idx in df.index[bad.to_numpy()]:
            results.append({
                "type": "Not expected type",
                "issue_type": "Not expected type",
                "row": row_idx + 2,
                "column": col_name,
                "value": df.at[row_idx, col_name]
            })

    return results


def check_numeric_range(df: pd.DataFrame, column_name, min_value, max_value) -> list:
    results = []

    if column_name not in df.columns:
        return results

    for row_idx in df.index:
        val = df.at[row_idx, column_name]

        if pd.isna(val):
            continue

        num = _to_number(val)
        if num is None:
            continue

        if min_value <= num <= max_value:
            continue
        else:
            issue = {
                "type": "Invalid range",
                "issue_type": "Invalid range",
                "row": row_idx + ROW_OFFSET,
                "column": column_name,
                "value": val
            }
            results.append(issue)
    return results


def check_allowed_values(df: pd.DataFrame, column_name, allowed_values) -> list:
    results = []

    if column_name not in df.columns:
        return results

    for row_idx in df.index:
        val = df.at[row_idx, column_name]

        if pd.isna(val):
            continue

        if val not in allowed_values:
            issue = {
                "type": "Invalid value",
                "issue_type": "Invalid value",
                "row": row_idx + ROW_OFFSET,
                "column": column_name,
                "value": val
            }
            results.append(issue)
    return results
