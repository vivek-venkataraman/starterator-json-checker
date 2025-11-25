import sys

import PySide6
from PySide6.QtWidgets import QApplication


from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QButtonGroup,
    QPushButton,
    QSpinBox,
    QCheckBox,
)

# Backend + computation modules
import verify_json
from GUI import load_pham_ids, update_all_local_jsons


class StarteratorMainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Starterator JSON Verification")

        # central widget and layout
        central = QWidget()
        main_layout = QVBoxLayout(central)
        self.setCentralWidget(central)

        # data source local vs network toggle
        source_layout = QVBoxLayout()
        source_label = QLabel("Data source for JSON files:")
        self.radio_online = QRadioButton("Download from server (with caching)")
        self.radio_local = QRadioButton("Use local JSON files only")
        self.radio_online.setChecked(True)  # default: network mode

        self.source_group = QButtonGroup(self)
        self.source_group.addButton(self.radio_online)
        self.source_group.addButton(self.radio_local)

        source_layout.addWidget(source_label)
        source_layout.addWidget(self.radio_online)
        source_layout.addWidget(self.radio_local)
        main_layout.addLayout(source_layout)

        # update the locally downloaded JSONs button
        self.update_button = QPushButton("Update local JSONs (redownload all)")
        main_layout.addWidget(self.update_button)

        # phams amt input
        pham_layout = QHBoxLayout()
        pham_layout.addWidget(QLabel("Total phams to check (0 = all):"))
        self.phams_spin = QSpinBox()
        self.phams_spin.setRange(0, 100000)
        self.phams_spin.setValue(500)  # match your default
        pham_layout.addWidget(self.phams_spin)
        main_layout.addLayout(pham_layout)

        # chunk size input
        chunk_layout = QHBoxLayout()
        chunk_layout.addWidget(QLabel("Chunk size for status updates:"))
        self.chunk_spin = QSpinBox()
        self.chunk_spin.setRange(1, 10000)
        self.chunk_spin.setValue(20)  # match your default
        chunk_layout.addWidget(self.chunk_spin)
        main_layout.addLayout(chunk_layout)

        # refresh toggle
        self.refresh_checkbox = QCheckBox("Refresh selected JSONs before verification")
        self.refresh_checkbox.setChecked(False)
        main_layout.addWidget(self.refresh_checkbox)

        # run button
        self.run_button = QPushButton("Run Verification")
        main_layout.addWidget(self.run_button)

        # status label
        self.status_label = QLabel("Ready")
        main_layout.addWidget(self.status_label)

        # connection signals
        self.update_button.clicked.connect(self.on_update_clicked)
        self.run_button.clicked.connect(self.on_run_clicked)

    # helpers for reading UI
    def get_current_settings_from_ui(self):
        """
        Read values from the widgets and return a simple dict
        of the settings we want to pass into verify_json.
        """
        use_network = self.radio_online.isChecked()
        phams_amount = self.phams_spin.value()
        if phams_amount == 0:
            phams_amount = None  # 0 means "all"

        chunk_size = self.chunk_spin.value()
        refresh_all = self.refresh_checkbox.isChecked()

        return {
            "use_network": use_network,
            "phams_amount": phams_amount,
            "chunk_size": chunk_size,
            "refresh_all": refresh_all,
        }

    # slots

    def on_update_clicked(self):
        """
        Called when 'Update local JSONs (redownload all)' is pressed.
        Uses the backend to reload JSONs for all pham IDs.
        """
        self.status_label.setText("Updating local JSON files...")
        self.repaint()  # force label refresh

        pham_ids = load_pham_ids()
        if not pham_ids:
            self.status_label.setText("No pham IDs found (check pham_ids.txt).")
            return

        try:
            update_all_local_jsons(pham_ids, force=True)
            self.status_label.setText("Local JSONs updated successfully.")
        except Exception as e:
            self.status_label.setText(f"Error updating JSONs: {e}")

    def on_run_clicked(self):
        """
        Called when 'Run Verification' is pressed.
        Sets options on verify_json and then calls verify_json.main().
        """
        settings = self.get_current_settings_from_ui()

        # Push settings into verify_json module globals
        verify_json.use_network = settings["use_network"]
        verify_json.refresh_all = settings["refresh_all"]
        verify_json.phams_amount = settings["phams_amount"]
        verify_json.chunk_size = settings["chunk_size"]

        mode = "network" if settings["use_network"] else "local"
        refresh_text = "with refresh" if settings["refresh_all"] else "no refresh"
        self.status_label.setText(f"Running verification ({mode}, {refresh_text})...")
        self.repaint()

        try:
            # NOTE: This will block the GUI until it finishes.
            # Later you can move this into a QThread if you want it non-blocking.
            verify_json.main()
            self.status_label.setText("Verification completed.")
        except Exception as e:
            self.status_label.setText(f"Error during verification: {e}")


def main():
    app = QApplication(sys.argv)
    window = StarteratorMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
