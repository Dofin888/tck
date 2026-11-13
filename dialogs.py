from PySide6.QtWidgets import (
    QInputDialog,
    QMessageBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QVBoxLayout,
    QComboBox,
)


# У всех функций одинаковое начало: (parent, df, ...)
# parent = окно, над которым открыть диалог; df = текущая таблица


def ask_column(parent, df, title):
    columns = [str(c) for c in df.columns]
    column, ok = QInputDialog.getItem(parent, title, "Колонка:", columns, 0, False)
    return column if ok else None


def ask_numeric_range(parent, df):
    column = ask_column(parent, df, "Числовой диапазон")
    if column is None:
        return None

    min_value, ok = QInputDialog.getInt(parent, "Числовой диапазон", "Минимум:", 1, -1000000, 1000000)
    if not ok:
        return None

    max_value, ok = QInputDialog.getInt(parent, "Числовой диапазон", "Максимум:", 100, -1000000, 1000000)
    if not ok:
        return None

    return {"column_name": column, "min_value": min_value, "max_value": max_value}


def ask_allowed_values(parent, df):
    column = ask_column(parent, df, "Допустимые значения")
    if column is None:
        return None

    text, ok = QInputDialog.getText(parent, "Допустимые значения", "Значения через запятую:")
    if not ok or not text.strip():
        return None

    allowed = [s.strip() for s in text.split(",") if s.strip()]
    return {"column_name": column, "allowed_values": allowed}


def ask_column_types(parent, df):
    dialog = QDialog(parent)
    dialog.setWindowTitle("Типы колонок")

    layout = QVBoxLayout(dialog)
    form = QFormLayout()

    combos = {}
    for column in df.columns:
        combo = QComboBox()
        combo.addItems(["Не проверять", "Number", "Text", "Date"])
        form.addRow(str(column), combo)
        combos[column] = combo

    layout.addLayout(form)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None

    config = {
        column: combo.currentText()
        for column, combo in combos.items()
        if combo.currentText() != "Не проверять"
    }

    if not config:
        QMessageBox.warning(parent, "Типы колонок", "Выбери тип хотя бы для одной колонки")
        return None

    return {"column_types_config": config}


def ask_params(parent, df, name):
    """Спросить параметры для проверки с названием name.
    Возвращает словарь параметров или None, если пользователь отменил."""
    if name == "Повторяющиеся значения":
        column = ask_column(parent, df, name)
        return None if column is None else {"column_name": column}
    if name == "Проверка типов данных":
        return ask_column_types(parent, df)
    if name == "Числовой диапазон":
        return ask_numeric_range(parent, df)
    if name == "Допустимые значения":
        return ask_allowed_values(parent, df)
    return None
