import sys
import os
import subprocess
import re
import shutil
import time
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QLabel, QTextEdit, QProgressBar,
                               QFileDialog, QMessageBox)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QTextCursor

class FFmpegWorker(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int)
    finished_signal = Signal(bool)

    def __init__(self, folder_path):
        super().__init__()
        self.folder_path = folder_path
        self.process = None

    def run(self):
        output_file = os.path.join(self.folder_path, "output.mp4")
        if os.path.exists(output_file):
            self.log_signal.emit("Overwriting existing output.mp4...")
            try:
                os.remove(output_file)
            except Exception as e:
                self.log_signal.emit(f"Error removing existing output.mp4: {e}")
                self.finished_signal.emit(False)
                return

        cmd = ["ffmpeg", "-y", "-i", "fixed.m3u8", "-c", "copy", "output.mp4"]
        
        try:
            self.log_signal.emit(f"Executing: {' '.join(cmd)}")
            
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            
            self.process = subprocess.Popen(
                cmd,
                cwd=self.folder_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="ignore",
                bufsize=1,
                creationflags=creationflags
            )

            duration_secs = 0
            duration_pattern = re.compile(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)")
            time_pattern = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")

            for line in self.process.stdout:
                line_stripped = line.strip()
                self.log_signal.emit(line_stripped)
                
                dur_match = duration_pattern.search(line_stripped)
                if dur_match:
                    h, m, s = map(float, dur_match.groups())
                    duration_secs = (h * 3600) + (m * 60) + s

                time_match = time_pattern.search(line_stripped)
                if time_match and duration_secs > 0:
                    h, m, s = map(float, time_match.groups())
                    current_secs = (h * 3600) + (m * 60) + s
                    progress = int((current_secs / duration_secs) * 100)
                    self.progress_signal.emit(max(0, min(progress, 100)))

            self.process.wait()
            
            if self.process.returncode == 0:
                self.progress_signal.emit(100)
                self.log_signal.emit(f"\nSuccess! Output saved at: {output_file}")
                self.finished_signal.emit(True)
            else:
                self.log_signal.emit(f"\nFFmpeg failed with return code {self.process.returncode}.")
                self.finished_signal.emit(False)

        except Exception as e:
            self.log_signal.emit(f"\nAn unexpected error occurred: {str(e)}")
            self.finished_signal.emit(False)


class HLSFixerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.folder_path = None
        self.worker = None
        self.start_time = 0
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("HLS Fixer")
        self.resize(650, 550)
        self.setAcceptDrops(True)
        
        self.setStyleSheet("""
            QWidget {
                background-color: #121212;
                color: #e0e0e0;
                font-family: Arial, sans-serif;
            }
            QPushButton {
                background-color: #333333;
                border: 1px solid #555555;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #444444;
            }
            QPushButton:disabled {
                background-color: #222222;
                color: #777777;
            }
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #007acc;
            }
            QTextEdit {
                background-color: #0a0a0a;
                border: 1px solid #333333;
                font-family: monospace;
                padding: 5px;
            }
        """)

        layout = QVBoxLayout()

        self.lbl_info = QLabel("Drop a folder with video chunks (.ts) or playlist (.m3u8)")
        self.lbl_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_info.setStyleSheet("font-size: 14px; font-weight: bold; padding: 15px;")
        layout.addWidget(self.lbl_info)

        btn_layout = QHBoxLayout()
        self.btn_select = QPushButton("Select Folder")
        self.btn_select.clicked.connect(self.select_folder)
        btn_layout.addWidget(self.btn_select)

        self.btn_fix = QPushButton("Fix & Merge")
        self.btn_fix.clicked.connect(self.run_ffmpeg)
        btn_layout.addWidget(self.btn_fix)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.cancel_process)
        self.btn_cancel.setEnabled(False)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        layout.addWidget(self.text_log)

        self.setLayout(layout)

    def log(self, message):
        self.text_log.append(message)
        self.text_log.moveCursor(QTextCursor.MoveOperation.End)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.set_folder(folder)

    def set_folder(self, folder_path):
        self.folder_path = os.path.normpath(folder_path)
        self.lbl_info.setText(f"Selected: {self.folder_path}")
        self.log(f"--- Folder selected: {self.folder_path} ---")
        self.progress_bar.setValue(0)

    def find_m3u8(self):
        if not self.folder_path:
            return None
        
        for file in os.listdir(self.folder_path):
            if file.lower().endswith(".m3u8") and file != "fixed.m3u8":
                return os.path.join(self.folder_path, file)
        return None

    def resolve_ts_path(self, line):
        direct_path = os.path.join(self.folder_path, line)
        if os.path.exists(direct_path):
            return line
            
        basename = os.path.basename(line)
        for root, dirs, files in os.walk(self.folder_path):
            if basename in files:
                found_path = os.path.join(root, basename)
                rel_path = os.path.relpath(found_path, self.folder_path)
                rel_path = rel_path.replace("\\", "/") 
                self.log(f"Auto-detected segment in subfolder: {rel_path}")
                return rel_path
                
        return line

    def fix_m3u8(self, original_m3u8):
        fixed_path = os.path.join(self.folder_path, "fixed.m3u8")
        ts_found = False
        missing_ts = []

        try:
            with open(original_m3u8, 'r', encoding='utf-8') as f_in:
                lines = f_in.readlines()

            with open(fixed_path, 'w', encoding='utf-8') as f_out:
                for line in lines:
                    stripped_line = line.strip()
                    if stripped_line.endswith(".ts"):
                        ts_filename = self.resolve_ts_path(stripped_line)
                        f_out.write(ts_filename + "\n")
                        ts_found = True
                        
                        ts_full_path = os.path.join(self.folder_path, ts_filename)
                        if not os.path.exists(ts_full_path):
                            missing_ts.append(ts_filename)
                    else:
                        f_out.write(stripped_line + "\n")
                        
            return fixed_path, ts_found, missing_ts
        except Exception as e:
            self.log(f"Error reading/writing .m3u8: {e}")
            return None, False, []

    def generate_m3u8_from_ts(self):
        if not self.folder_path:
            return None, False, []

        ts_files = []
        for root, dirs, files in os.walk(self.folder_path):
            for f in files:
                if f.lower().endswith('.ts'):
                    rel_path = os.path.relpath(os.path.join(root, f), self.folder_path)
                    rel_path = rel_path.replace("\\", "/")
                    ts_files.append(rel_path)

        if not ts_files:
            return None, False, []

        ts_files.sort(key=lambda x: [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', x)])

        fixed_path = os.path.join(self.folder_path, "fixed.m3u8")
        try:
            with open(fixed_path, 'w', encoding='utf-8') as f_out:
                f_out.write("#EXTM3U\n")
                for ts in ts_files:
                    f_out.write("#EXTINF:1.0,\n")
                    f_out.write(ts + "\n")
            return fixed_path, True, []
        except Exception as e:
            self.log(f"Error generating .m3u8: {e}")
            return None, False, []

    def run_ffmpeg(self):
        if self.worker and self.worker.isRunning():
            return

        if not self.folder_path:
            QMessageBox.warning(self, "Error", "Please select a folder first.")
            return

        if not shutil.which("ffmpeg"):
            self.log("Error: FFmpeg not found in PATH.")
            QMessageBox.critical(self, "Error", "FFmpeg is not installed or not available in PATH.\nPlease install FFmpeg to proceed.")
            return

        ts_found_anywhere = False
        for root, dirs, files in os.walk(self.folder_path):
            if any(f.lower().endswith('.ts') for f in files):
                ts_found_anywhere = True
                break
                
        if not ts_found_anywhere:
            self.log("Error: No .ts files found in folder or subfolders.")
            QMessageBox.critical(self, "Error", "No .ts files found in the folder or subfolders.")
            return

        self.text_log.clear()
        self.progress_bar.setValue(0)
        self.log("Starting process...")
        self.start_time = time.time()

        m3u8_file = self.find_m3u8()
        if m3u8_file:
            self.log(f"Found playlist: {os.path.basename(m3u8_file)}")
            fixed_m3u8, ts_found, missing_ts = self.fix_m3u8(m3u8_file)
        else:
            self.log("No playlist found — automatically building video from .ts files.")
            fixed_m3u8, ts_found, missing_ts = self.generate_m3u8_from_ts()

        if not fixed_m3u8 or not ts_found:
            self.log("Error: No .ts files found or referenced.")
            QMessageBox.critical(self, "Error", "No .ts files found in the folder.")
            return

        self.log(f"Successfully generated fixed.m3u8.")
        
        if missing_ts:
            self.log(f"Warning: {len(missing_ts)} referenced .ts files are missing from the folder!")
            for missing in missing_ts[:5]:
                self.log(f" - Missing: {missing}")
            if len(missing_ts) > 5:
                self.log(f" - ...and {len(missing_ts) - 5} more.")

        self.btn_fix.setEnabled(False)
        self.btn_select.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        
        self.log("Processing... please wait")

        self.worker = FFmpegWorker(self.folder_path)
        self.worker.log_signal.connect(self.log)
        self.worker.progress_signal.connect(self.progress_bar.setValue)
        self.worker.finished_signal.connect(self.on_ffmpeg_finished)
        self.worker.start()

    def cancel_process(self):
        if self.worker and self.worker.isRunning():
            if self.worker.process:
                self.worker.process.kill()
                
            self.worker.terminate()
            self.worker.wait()
            self.log("\nProcess cancelled by user.")
            
            self.btn_fix.setEnabled(True)
            self.btn_select.setEnabled(True)
            self.btn_cancel.setEnabled(False)

    def on_ffmpeg_finished(self, success):
        self.btn_fix.setEnabled(True)
        self.btn_select.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        
        elapsed = time.time() - self.start_time
        self.log(f"Completed in {int(elapsed)} seconds")
        
        if success:
            QMessageBox.information(self, "Success", "Video merged successfully into output.mp4")
            
            try:
                if sys.platform == "win32":
                    os.startfile(self.folder_path)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", self.folder_path])
                else:
                    subprocess.Popen(["xdg-open", self.folder_path])
            except Exception as e:
                self.log(f"Could not open folder automatically: {e}")
        else:
            QMessageBox.warning(self, "Failed", "FFmpeg process failed. Check logs for details.")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            path = urls[0].toLocalFile()
            if os.path.isdir(path):
                self.set_folder(path)
            else:
                self.set_folder(os.path.dirname(path))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HLSFixerApp()
    window.show()
    sys.exit(app.exec())