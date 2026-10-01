import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QSettings

from db.database import init_db
from ui.main_window import MainWindow
from ui import i18n
from ui.theme import theme


def main():
    init_db()

    # Load the saved language (default Arabic on first run).
    settings = QSettings("MembershipSystem", "app")
    lang = settings.value("language", "ar")
    i18n.load(lang)

    app = QApplication(sys.argv)

    # RTL if the loaded language is right-to-left.
    if i18n.is_rtl():
        app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    else:
        app.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

    theme().apply(app)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()