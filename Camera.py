import sys
import warnings
from datetime import datetime
try:
    from PyQt4 import QtGui, QtCore, Qt
except Exception, details:
    print 'Unfortunately, your system misses the PyQt4 packages.'
    quit()
from VideoRecording import VideoRecording
from default_config import default_template, camera_device_search_range, camera_name_format, frames_per_second,\
    width, height, max_tab_width, min_tab_width, offset_left, offset_top

__author__ = 'Fabian Sinz, Joerg Henninger'
import cv2

def brg2rgb(frame):
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

def brg2grayscale(frame):
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

class Camera(QtCore.QObject):
    def __init__(self, device_no=0, post_processor=None, parent=None):
        """
        Initializes a new camera

        :param post_processor: function that is applies to the frame after grabbing
        """
        QtCore.QObject.__init__(self, parent)

        self.capture = None
        self.device_no = device_no
        self.name = None
        self.recording = None
        self.post_processor = post_processor
        if post_processor is None:
            self.post_processor = lambda x, y, z: (x, y, z)

        # DEBUG
        # self.last_frame = datetime.now()
        # self.min = 1000.

        self.open()

        # create timer for independent frame acquisition
        self.timer = QtCore.QTimer()
        self.connect(self.timer, QtCore.SIGNAL('timeout()'), self.grab_frame)

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def open(self):
        capture = cv2.VideoCapture(self.device_no)
        self.capture = capture
        
        # try to increase the resolution of the frame capture; default is 640x480
        #~ self.capture.set(cv2.cv.CV_CAP_PROP_FRAME_WIDTH, 864)
        #~ self.capture.set(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT, 480)
        self.capture.set(cv2.cv.CV_CAP_PROP_FRAME_WIDTH, 1280)
        self.capture.set(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT, 720)

    def is_working(self):
        return self.capture.isOpened()

    def get_properties(self):
        """
        :returns: the properties (cv2.cv.CV_CAP_PROP_*) from the camera
        :rtype: dict
        """
        if self.capture is not None:
            properties = [e for e in dir(cv2.cv) if "CV_CAP_PROP" in e]
            ret = {}
            for e in properties:
                ret[e[12:].lower()] = self.capture.get(getattr(cv2.cv, e))
            return ret
        else:
            warnings.warn("Camera needs to be opened first!")
            return None

    def get_resolution(self):
        if self.capture is not None:
            return int(self.capture.get(cv2.cv.CV_CAP_PROP_FRAME_WIDTH)), \
                   int(self.capture.get(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT))
        else:
            raise ValueError("Camera is not opened or not functional! Capture is None")

    def grab_frame(self):
        
        flag, frame = self.capture.read()
        dtime = datetime.now()

        # post-processing
        if self.color:
            frame = brg2rgb(frame)
        else:
            frame = brg2grayscale(frame)

        # DEBUG
        # gap = 1000.*(dtime - self.last_frame).total_seconds()
        # if self.min > gap:
        #     self.min = gap
        # sys.stdout.write('\rframerate: {0:3.2f} ms{1:s}; min:{2:3.2f}'.format(gap, 5*' ', self.min,5*' '))
        # sys.stdout.flush()
        # self.last_frame = dtime

        if not flag:
            warnings.warn("Coulnd't grab frame from camera!")
            return None

        # emit signal with frame and dtime
        self.emit(QtCore.SIGNAL("NewFrame(PyQt_PyObject)"), self.post_processor(self.name, frame, dtime))

    def create_and_start_new_recording(self, trial_name):
        
        self.recording = VideoRecording('{0}_{1}.avi'.format(trial_name, self.name),
                                        '{0}_{1}_metadata.dat'.format(trial_name, self.name),
                                        self.get_resolution(),
                                        frames_per_second,
                                        'XVID',
                                        color=False)

        self.recordingThread = QtCore.QThread(parent=self)
        self.recording.moveToThread(self.recordingThread)
        self.recordingThread.start()
        self.connect(self, QtCore.SIGNAL("NewFrame(PyQt_PyObject)"), self.recording.write)

    def start_capture(self):
        self.timer.start(5)  # 5 msec

    def stop_capture(self):
        self.timer.stop()

    def stop_recording(self):
        self.recordingThread.quit()
        self.recordingThread.wait()
        self.recording = None
        self.recordingThread = None

    def close(self):
        pass

