import os
import sys
import json
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from cheks import (
    check_allowed_values,
    check_numeric_range,
    find_duplicated_rows,
    find_duplicated_values,
    find_empty_or_whitespace_cells,
    validate_dataframe_types,
)
from dialogs import ask_params
from file_reader import load_table

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")
PREVIEW_LIMIT = 500

# =====================================================================
# Приложение и окно
# =====================================================================
app = QApplication(sys.argv)


def resource_path(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


with open(resource_path("style.qss"), "r", encoding="utf-8") as f:
    app.setStyleSheet(f.read())

app.setWindowIcon(QIcon(resource_path("tck.ico")))

window = QMainWindow()
window.setWindowTitle("Tck")
window.resize(1000, 750)

central_widget = QWidget()
window.setCentralWidget(central_widget)
main_layout = QVBoxLayout(central_widget)

# =====================================================================
# Состояние программы
# =====================================================================
current_df = None  # открытая таблица
current_file_path = None  # путь к открытому файлу
check_params = {}  # название проверки -> её параметры
check_boxes = {}  # название проверки -> чекбокс
last_issues = None  # результат последней проверки (None = проверка ещё не запускалась)

CHECKS = [
    "Пустые значения",
    "Полные дубликаты строк",
    "Повторяющиеся значения",
    "Проверка типов данных",
    "Числовой диапазон",
    "Допустимые значения",
]

# проверки, которым нужны параметры от пользователя
PARAM_CHECKS = [
    "Повторяющиеся значения",
    "Проверка типов данных",
    "Числовой диапазон",
    "Допустимые значения",
]

# =====================================================================
# Панель инструментов
# =====================================================================
toolbar = QHBoxLayout()

open_button = QPushButton("Открыть файл")
sheet_label = QLabel("Лист:")
sheet_selector = QComboBox()
reset_button = QPushButton("Сбросить настройки")
run_button = QPushButton("Запустить проверку")
export_button = QPushButton("Экспорт результатов")

toolbar.addWidget(open_button)
toolbar.addWidget(sheet_label)
toolbar.addWidget(sheet_selector)
toolbar.addWidget(reset_button)
toolbar.addWidget(export_button)
toolbar.addStretch()
toolbar.addWidget(run_button)

main_layout.addLayout(toolbar)

# =====================================================================
# Центральная часть: предпросмотр + список проверок
# =====================================================================
middle_splitter = QSplitter(Qt.Orientation.Horizontal)

preview_group = QGroupBox("Предпросмотр таблицы")
preview_layout = QVBoxLayout(preview_group)
preview_table = QTableWidget(0, 0)
preview_layout.addWidget(preview_table)

checks_group = QGroupBox("Проверки")
checks_layout = QVBoxLayout(checks_group)

for check_name in CHECKS:
    checkbox = QCheckBox(check_name)
    checkbox.setChecked(True)
    checks_layout.addWidget(checkbox)
    check_boxes[check_name] = checkbox

checks_layout.addStretch()

middle_splitter.addWidget(preview_group)
middle_splitter.addWidget(checks_group)
middle_splitter.setStretchFactor(0, 3)
middle_splitter.setStretchFactor(1, 1)

# =====================================================================
# Нижняя часть: результаты
# =====================================================================
results_group = QGroupBox("Результаты проверки")
results_layout = QVBoxLayout(results_group)

results_table = QTableWidget(0, 4)
results_table.setHorizontalHeaderLabels(["Тип проблемы", "Строка", "Столбец", "Значение"])
results_layout.addWidget(results_table)

main_splitter = QSplitter(Qt.Orientation.Vertical)
main_splitter.addWidget(middle_splitter)
main_splitter.addWidget(results_group)
main_splitter.setStretchFactor(0, 3)
main_splitter.setStretchFactor(1, 1)

main_layout.addWidget(main_splitter)


# =====================================================================
# Вспомогательные функции
# =====================================================================
def to_text(value):
    """Значение ячейки -> текст для таблицы (пустое и None становятся '')."""
    if value is None or pd.isna(value):
        return ""
    return str(value)


def show_results(issues):
    results_table.setRowCount(len(issues))

    for i, issue in enumerate(issues):
        results_table.setItem(i, 0, QTableWidgetItem(to_text(issue.get("type"))))
        results_table.setItem(i, 1, QTableWidgetItem(to_text(issue.get("row"))))
        results_table.setItem(i, 2, QTableWidgetItem(to_text(issue.get("column"))))
        results_table.setItem(i, 3, QTableWidgetItem(to_text(issue.get("value"))))


def table_key(df):
    return "|".join(str(c) for c in df.columns)


def read_settings():
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_settings(data):
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_settings():
    data = read_settings()
    data[table_key(current_df)] = check_params
    write_settings(data)


def get_settings_path():
    folder = os.path.join(os.environ.get("APPDATA", os.path.dirname(os.path.abspath(__file__))), "Tck")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "settings.json")


SETTINGS_PATH = get_settings_path()


# =====================================================================
# Загрузка файла и листа
# =====================================================================
def open_file():
    """Выбрать файл, заполнить список листов, загрузить лист."""
    global current_file_path

    file_path, _ = QFileDialog.getOpenFileName(
        window, "Открыть таблицу", "", "Таблицы (*.csv *.xlsx)"
    )
    if not file_path:
        return

    try:
        sheet_selector.blockSignals(True)  # заполнение списка не должно вызывать загрузку
        sheet_selector.clear()

        if file_path.lower().endswith(".xlsx"):
            sheet_selector.addItems(pd.ExcelFile(file_path).sheet_names)
            sheet_selector.setEnabled(True)
        else:
            sheet_selector.addItem("—")
            sheet_selector.setEnabled(False)

        sheet_selector.blockSignals(False)
        current_file_path = file_path
        load_current_sheet()

    except Exception as e:
        sheet_selector.blockSignals(False)
        QMessageBox.critical(window, "Ошибка", str(e))


def load_current_sheet():
    """Прочитать выбранный лист и показать его в предпросмотре."""
    global current_df, last_issues

    if current_file_path is None:
        return

    try:
        sheet = sheet_selector.currentText() if sheet_selector.isEnabled() else 0
        df = load_table(current_file_path, sheet_name=sheet)

        current_df = df
        check_params.clear()
        saved = read_settings().get(table_key(df), {})
        check_params.update(saved)

        preview_df = df.head(PREVIEW_LIMIT)

        preview_table.setRowCount(len(preview_df))
        preview_table.setColumnCount(len(df.columns))
        preview_table.setHorizontalHeaderLabels([str(c) for c in df.columns])
        preview_table.setVerticalHeaderLabels([str(i + 2) for i in range(len(preview_df))])

        for row in range(len(preview_df)):
            for col in range(len(df.columns)):
                preview_table.setItem(row, col, QTableWidgetItem(to_text(preview_df.iat[row, col])))

        if len(df) > PREVIEW_LIMIT:
            window.statusBar().showMessage(
                f"Показаны первые {PREVIEW_LIMIT} строк из {len(df)}. Проверка идёт по всей таблице."
            )

    except Exception as e:
        QMessageBox.critical(window, "Ошибка", str(e))


# =====================================================================
# Запуск проверок
# =====================================================================
def collect_issues(selected):
    """Запустить отмеченные проверки, вернуть общий список проблем."""
    all_issues = []

    if "Пустые значения" in selected:
        all_issues.extend(find_empty_or_whitespace_cells(current_df))

    if "Полные дубликаты строк" in selected:
        all_issues.extend(find_duplicated_rows(current_df))

    if "Повторяющиеся значения" in selected:
        all_issues.extend(find_duplicated_values(current_df, **check_params["Повторяющиеся значения"]))

    if "Проверка типов данных" in selected:
        all_issues.extend(validate_dataframe_types(current_df, **check_params["Проверка типов данных"]))

    if "Числовой диапазон" in selected:
        all_issues.extend(check_numeric_range(current_df, **check_params["Числовой диапазон"]))

    if "Допустимые значения" in selected:
        all_issues.extend(check_allowed_values(current_df, **check_params["Допустимые значения"]))

    return all_issues


def run_checks():
    global last_issues
    if current_df is None:
        QMessageBox.warning(window, "Нет файла", "Сначала открой файл")
        return

    selected = [name for name, cb in check_boxes.items() if cb.isChecked()]
    if not selected:
        QMessageBox.information(window, "Нет проверок", "Отметь хотя бы одну проверку")
        return

    # Этап 1: спросить недостающие параметры (отмена = ничего не запускаем)
    asked_new = False
    for name in selected:
        if name in PARAM_CHECKS and name not in check_params:
            params = ask_params(window, current_df, name)
            if params is None:
                return
            check_params[name] = params
            asked_new = True

        if asked_new:
            save_settings()

    # Этап 2: запустить проверки и показать результат
    try:
        all_issues = collect_issues(selected)
    except Exception as e:
        QMessageBox.critical(window, "Ошибка проверки", str(e))
        return

    last_issues = all_issues
    show_results(all_issues)

    if all_issues:
        message = f"Запущено проверок: {len(selected)}. Найдено проблем: {len(all_issues)}"
    else:
        message = f"Запущено проверок: {len(selected)}. Проблем не найдено"
    window.statusBar().showMessage(message)


def reset_params():
    if current_df is None:
        check_params.clear()
        return

    count = len(check_params)
    check_params.clear()

    data = read_settings()
    data.pop(table_key(current_df), None)
    write_settings(data)

    if count:
        QMessageBox.information(
            window, "Настройки сброшены",
            f"Сброшено настроек: {count}. При следующем запуске параметры спросят заново."
        )
    else:
        QMessageBox.information(window, "Сброс", "Сохранённых настроек нет, сбрасывать нечего.")


def export_results():
    if last_issues is None:
        QMessageBox.warning(window, "Нет результатов", "Сначала запусти проверку")
        return
    if not last_issues:
        QMessageBox.information(window, "Нечего экспортировать", "Проблем не найдено")
        return

    path, selected_filter = QFileDialog.getSaveFileName(
        window, "Сохранить результаты", "результаты_проверки",
        "Excel (*.xlsx);;CSV (*.csv)"
    )
    if not path:
        return

    # если расширение не указано, берём по выбранному фильтру
    if not path.lower().endswith((".xlsx", ".csv")):
        path += ".xlsx" if "xlsx" in selected_filter else ".csv"

    try:
        df = pd.DataFrame(last_issues)[["type", "row", "column", "value"]]
        df.columns = ["Тип проблемы", "Строка", "Столбец", "Значение"]

        if path.lower().endswith(".xlsx"):
            df.to_excel(path, index=False)
        else:
            df.to_csv(path, index=False, encoding="utf-8-sig")

        window.statusBar().showMessage(f"Результаты сохранены: {path}", 5000)
    except Exception as e:
        QMessageBox.critical(window, "Ошибка экспорта", str(e))


# =====================================================================
# Подключение сигналов (все связки в одном месте)
# =====================================================================
open_button.clicked.connect(open_file)
run_button.clicked.connect(run_checks)
reset_button.clicked.connect(reset_params)
sheet_selector.currentTextChanged.connect(load_current_sheet)
export_button.clicked.connect(export_results)

# =====================================================================
# Запуск
# =====================================================================
window.show()
sys.exit(app.exec())
