"""Windows GUI. Run: python app.py"""
import sys
from pathlib import Path
from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QLabel, QPushButton, QFileDialog, QProgressBar, QPlainTextEdit, QMessageBox,
    QDoubleSpinBox, QSpinBox, QCheckBox)
from core import BackupOptions, Cancelled, run_backup, normalize_url

class Worker(QObject):
    event = Signal(str, object)
    finished = Signal()
    def __init__(self, options):
        super().__init__()
        self.options = options
        self.cancelled = False
    @Slot()
    def run(self):
        try:
            run_backup(self.options, lambda typ, payload: self.event.emit(typ, payload), lambda: self.cancelled)
        except Cancelled:
            self.event.emit('status', '停止しました。完了分は保存済みです。')
        except Exception as e:
            self.event.emit('error', str(e))
        finally:
            self.finished.emit()

class Main(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('uploader.jp Backup Tool - Preview')
        self.resize(740, 510)
        self.thread = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('公開アップローダーURL'))
        self.url = QLineEdit()
        self.url.setPlaceholderText('https://ux.getuploader.com/アップローダー名/')
        layout.addWidget(self.url)
        layout.addWidget(QLabel('保存先フォルダー'))
        line = QHBoxLayout()
        self.folder = QLineEdit(str(Path.home() / 'Downloads'))
        line.addWidget(self.folder)
        browse = QPushButton('参照…')
        browse.clicked.connect(self.browse)
        line.addWidget(browse)
        layout.addLayout(line)
        line = QHBoxLayout()
        line.addWidget(QLabel('アクセス間隔（秒）'))
        self.interval = QDoubleSpinBox()
        self.interval.setRange(2.0, 120.0)
        self.interval.setValue(3.0)
        self.interval.setSingleStep(0.5)
        line.addWidget(self.interval)
        line.addWidget(QLabel('最大走査ページ数'))
        self.pages = QSpinBox()
        self.pages.setRange(1, 2000)
        self.pages.setValue(300)
        line.addWidget(self.pages)
        layout.addLayout(line)
        self.agree = QCheckBox('利用規約・著作権・公開範囲を確認し、取得権限のある公開ファイルのみ保存する')
        layout.addWidget(self.agree)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.status = QLabel('待機中')
        layout.addWidget(self.status)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, 1)
        line = QHBoxLayout()
        self.start = QPushButton('一括ダウンロード開始')
        self.start.clicked.connect(self.begin)
        self.stop = QPushButton('停止')
        self.stop.setEnabled(False)
        self.stop.clicked.connect(self.cancel)
        line.addWidget(self.start)
        line.addWidget(self.stop)
        layout.addLayout(line)
    def browse(self):
        folder = QFileDialog.getExistingDirectory(self, '保存先を選択', self.folder.text())
        if folder: self.folder.setText(folder)
    def begin(self):
        if not self.agree.isChecked():
            QMessageBox.warning(self, '確認', '利用規約と取得権限を確認してください。')
            return
        try:
            normalize_url(self.url.text())
            opts = BackupOptions(self.url.text(), Path(self.folder.text()), self.interval.value(), self.pages.value())
            if not opts.folder.exists() or not opts.folder.is_dir():
                raise ValueError('保存先に既存のフォルダーを指定してください。')
        except Exception as e:
            QMessageBox.warning(self, '入力エラー', str(e))
            return
        self.start.setEnabled(False)
        self.stop.setEnabled(True)
        self.progress.setRange(0, 0)
        self.log.clear()
        self.thread = QThread()
        self.worker = Worker(opts)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.event.connect(self.handle)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.done)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()
    def cancel(self):
        if hasattr(self, 'worker'):
            self.worker.cancelled = True
            self.stop.setEnabled(False)
            self.status.setText('停止要求を受け付けました。現在の処理が終わると停止します。')
    @Slot(str, object)
    def handle(self, kind, data):
        if kind == 'total':
            self.progress.setRange(0, data)
            self.progress.setValue(0)
        elif kind == 'progress':
            idx, state, detail = data
            self.progress.setValue(idx)
            self.log.appendPlainText(f'[{state}] {detail}')
        elif kind == 'error':
            self.status.setText('エラー：' + data)
            self.log.appendPlainText('[error] ' + data)
        elif kind == 'status':
            self.status.setText(data)
            self.log.appendPlainText(data)
    @Slot()
    def done(self):
        self.start.setEnabled(True)
        self.stop.setEnabled(False)
        if self.progress.maximum() == 0:
            self.progress.setRange(0, 1)
            self.progress.setValue(0)
    def closeEvent(self, e):
        if self.thread and self.thread.isRunning():
            QMessageBox.information(self, '実行中', '先に停止ボタンを押してください。')
            e.ignore()
        else:
            e.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = Main()
    win.show()
    sys.exit(app.exec())
