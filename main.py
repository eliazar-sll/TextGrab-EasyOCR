import sys
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QPoint, QRect
from PyQt5.QtGui import QKeySequence, QIcon, QColor, QPainter, QPen, QCursor
from PyQt5.QtWidgets import QMainWindow, QApplication, QSystemTrayIcon, QMenu, QAction
from pynput.mouse import Controller

from PIL import ImageGrab, Image
import numpy as np

import easyocr

# import sentry_sdk
# sentry_sdk.init(
#     dsn="https://8ae9b6a81c9a45c89d565966ef7b14d7@o1286329.ingest.sentry.io/4503969478279168",

#     # Set traces_sample_rate to 1.0 to capture 100%
#     # of transactions for performance monitoring.
#     # We recommend adjusting this value in production.
#     traces_sample_rate=1.0
# )

# error screenshot -> maybe related with the discoloration of the result image

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)


class App(QSystemTrayIcon):
    # isProcessing = False

    def __init__(self):
        super().__init__()

        self.initUI()
        # self.initOCR()
        self.snipWidget = SnipWidget(self)
        self.snipWidget.snipped.connect(self.returnSnip)
        self.show()

    def initUI(self):
        # self.setWindowTitle("LaTeX OCR")
        # QApplication.setWindowIcon(QtGui.QIcon(':/icons/icon.svg'))

        # Create snip button
        self.menu = QMenu()

        self.snipButton = QAction('Snip [Alt+S]', self)
        self.snipButton.triggered.connect(self.onClick)
        self.snipButton.setShortcut(QKeySequence(Qt.Key_Alt | Qt.Key_S))

        # self.shortcut = QShortcut(QKeySequence("Alt+S"), self)
        # self.shortcut.activated.connect(self.onClick)

        # Create retry button
        self.closeButton = QAction('Close', self)
        self.closeButton.triggered.connect(QApplication.quit)

        self.menu.addAction(self.snipButton)
        self.menu.addAction(self.closeButton)

        # Create layout
        # buttons = QVBoxLayout()
        # buttons.addWidget(self.snipButton)
        # buttons.addWidget(self.closeButton)
        # self.setLayout(buttons)

        # Adding item on the menu bar
        # self.tray = QSystemTrayIcon()
        self.setIcon(QIcon("ocr.png"))
        self.setVisible(True)
        self.setContextMenu(self.menu)

    def initOCR(self):
        # self.reader = "OCR"
        self.reader = easyocr.Reader(['en'])

    def onClick(self):
        # self.showMinimized()
        self.snipWidget.snip()

    def returnPrediction(self, result):
        print(f"result: {result}")

        clipboard = QApplication.clipboard()
        clipboard.clear()
        clipboard.setText(result, clipboard.Clipboard)

    def returnSnip(self, img):
        # Run the model in a separate thread
        self.thread_ = ModelThread(self, img)
        self.thread_.finished.connect(self.returnPrediction)
        self.thread_.finished.connect(self.thread_.deleteLater)
        self.thread_.start()


class ModelThread(QThread):
    finished = pyqtSignal(str)

    def __init__(self, parent, img):
        super().__init__()
        self.img : np.ndarray= img
        self.parent_ = parent

    def run(self):
        print("Running...")
        
        im = Image.fromarray(self.img)
        im.save("screenshot.png")

        # print(f"{self.img.width}x{self.img.height}")
        result = self.parent_.reader.readtext(self.img, detail=0, min_size=0, low_text=0.3)
        str_result = " ".join(result)
        self.finished.emit(str_result)


class SnipWidget(QMainWindow):
    isSnipping = False
    snipped = pyqtSignal(np.ndarray)

    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        self.begin = QPoint()
        self.end = QPoint()

        self.mouse = Controller()

    def snip(self):
        self.isSnipping = True
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        QApplication.setOverrideCursor(QCursor(Qt.CrossCursor))

        # self.show()
        self.showFullScreen()

    def paintEvent(self, event):
        if self.isSnipping:
            brushColor = (0, 180, 255, 100)
            opacity = 0.3
        else:
            brushColor = (255, 255, 255, 0)
            opacity = 0

        self.setWindowOpacity(opacity)
        qp = QPainter(self)
        qp.setPen(QPen(QColor('black'), 2))
        qp.setBrush(QColor(*brushColor))
        qp.drawRect(QRect(self.begin, self.end))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            QApplication.restoreOverrideCursor()
            self.close()
            self.parent.show()
        event.accept()

    def mousePressEvent(self, event):
        self.startPos = self.mouse.position

        self.begin = event.pos()
        self.end = self.begin
        self.update()

    def mouseMoveEvent(self, event):
        self.end = event.pos()
        self.update()

    def mouseReleaseEvent(self, event):
        self.isSnipping = False        
        QApplication.restoreOverrideCursor()

        startPos = self.startPos
        endPos = self.mouse.position
        # account for retina display. #TODO how to check if device is actually using retina display
        factor = 2 if sys.platform == "darwin" else 1

        x1 = int(min(startPos[0], endPos[0])*factor)
        y1 = int(min(startPos[1], endPos[1])*factor)
        x2 = int(max(startPos[0], endPos[0])*factor)
        y2 = int(max(startPos[1], endPos[1])*factor)

        width = x2 - x1
        height = y2 - y1

        self.close()
        self.repaint()
        QApplication.processEvents()
        # try:
        #     img = ImageGrab.grab(bbox=(x1, y1, x2, y2), all_screens=True)
        # except Exception as e:
        #     if sys.platform == "darwin":
        #         img = ImageGrab.grab(bbox=(x1//factor, y1//factor, x2//factor, y2//factor), all_screens=True)
        #     else:
        #         raise e

        try:
            pixmap = QApplication.primaryScreen().grabWindow(0, x1, y1, width, height)
            channel_count = 4
            image = pixmap.toImage()

            b = image.bits()
            b.setsize(height * width * channel_count)

            np_array = np.frombuffer(b, np.uint8).reshape((height, width, channel_count))

        except Exception as e:
            print(e)
            
        QApplication.processEvents()

        self.begin = QPoint()
        self.end = QPoint()

        self.close()
        # self.parent.returnSnip(np.array(img))
        # self.snipped.emit(np.array(np_array)) # -> pil to np
        self.snipped.emit(np_array)

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    ex = App()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

