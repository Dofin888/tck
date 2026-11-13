import os
import python_calamine
import pandas as pd


# this funct load files for check
def load_table(file_path, sheet_name=None):
    # check if file doesn't exist
    if not os.path.exists(file_path):
        raise FileNotFoundError("File not found")

    # get file extension
    ext = os.path.splitext(file_path)[1].lower()

    # file reading
    try:
        if ext == ".csv":
            return pd.read_csv(file_path)
        elif ext == ".xlsx":
            try:
                EXCEL_ENGINE = "calamine"
            except ImportError:
                EXCEL_ENGINE = None  # None = стандартный openpyxl

            return pd.read_excel(file_path, sheet_name=sheet_name, engine=EXCEL_ENGINE)
        else:
            raise ValueError("Unsupported file type")

    except Exception as e:
        raise ValueError(f"Error reading file: {e}") from e


# get sheet names(lists)
def get_sheet_name(file_path):
    sheet_name = pd.ExcelFile("TestData/tck_test_data.xlsx")

    print(sheet_name.sheet_names)
