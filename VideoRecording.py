__author__ = 'Fabian Sinz, Joerg Henninger'

import cv2
import cv
import cPickle as pickle
try:
    from PyQt4 import QtGui, QtCore, Qt
except Exception, details:
    print 'Unfortunately, your system misses the PyQt4 packages.'
    quit()

class VideoRecording(QtCore.QObject):

    def __init__(self, filename, filename_metadata, resolution, fps, codec, color=True, parent=None):
        QtCore.QObject.__init__(self, parent)
        self.filename_metadata = filename_metadata
        self.writer = cv2.VideoWriter(filename, cv.CV_FOURCC(*codec), int(fps), resolution, color)

    def write(self, data):
        frame = data[1]
        dtime = data[2]
        self.writer.write(frame)
        self.write_metadata(dtime)

    def write_metadata(self, current_datetime):
        with open(self.filename_metadata, 'ab') as f:
            pickle.dump(current_datetime, f)
            f.flush()
