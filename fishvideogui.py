#! /usr/bin/env python

import sys
import os
import glob
try:
    from PyQt4 import QtGui, QtCore, Qt
except Exception, details:
    print 'Unfortunately, your system misses the PyQt4 packages.'
    quit()
from optparse import OptionParser
from default_config import default_template, camera_device_search_range, camera_name_format, frames_per_second,\
    width, height, max_tab_width, min_tab_width, offset_left, offset_top

sys.path.append('../')
from datetime import date, datetime, timedelta
from VideoCanvas import VideoCanvas
from MetadataTab import MetadataTab
import numpy as np
from PIL import Image as image
from PIL import ImageQt as iqt
from Camera import Camera, brg2rgb, brg2grayscale
__author__ = 'Joerg Henninger, Jan Grewe, Fabian Sinz'

# #######################################
'''
Note:
QMainWindow allows for funky things like menu- and tool-bars

Keyboard Shortcuts:
# Quit Program: ESC
# Next Metadata-Tab: CTRL+Page-Down
# Previous Metadata-Tab: CTRL+Page-UP

== OPTIONS ==
-u --template      -- choose your template by its name
-k --stop_time      -- define a stop time for your recording; Formats: "HH:MM:SS" and "YY-mm-dd HH:MM:SS"
-o --output_directory       -- define the output directory of your recordings
-s --instant_start         -- start the recording instantly without user input
-i --idle_screen        -- do not display the video frames; this saves quite some computational power
'''

# #######################################

# TODO video-canvas: full screen does not work properly. why?
# TODO Key bindings for start and stop of recording
# TODO validation of meta data tabs. Warn, if info is missing!

# #######################################

# import os
try:
    import odml
except:
    sys.path.append('/usr/lib/python2.7/site-packages')
    try:
        import odml
    except:
        print 'Cannot import odml library for metadata support! Check https://github.com/G-Node/python-odml'
        quit()

# #######################################
# THE MAIN GUI WINDOW


class Main(QtGui.QMainWindow):
    def __init__(self, app, options=None, parent=None):
        QtGui.QMainWindow.__init__(self, parent)
        self.app = app
        self.metadata_tabs = dict()
        self.trial_counter = 0
        self.output_dir = '.'
        self.data_dir = '.'
        self.event_list = odml.Section('events', 'event_list')
        self.record_timestamp = None
        self.color = False
        # #######################################
        self.setGeometry(offset_left, offset_top, width, height)
        self.setSizePolicy(Qt.QSizePolicy.Maximum, Qt.QSizePolicy.Maximum)
        self.setMinimumSize(width, height)
        self.setWindowTitle('Fish Video GUI')

        # #######################################

        self.video_recordings = dict()

        # #######################################
        # HANDLE OPTIONS

        default_xml_template = default_template
        self.idle_screen = False
        self.instant_start = False
        self.programmed_stop = False
        self.programmed_stop_datetime = None
        self.starttime = None
        self.is_recording = False

        if options:
            # template selection
            if options.template:
                template_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'templates')
                optional_template = os.path.join(template_path, options.template)
                if os.path.exists(optional_template):
                    default_xml_template = optional_template
                    print 'Template chosen: {0:s}'.format(os.path.basename(default_xml_template))
                else:
                    print 'Error: chosen template does not exist'
                    quit()

            # programmed stop-time
            if options.stop_time:
                try:
                    a = datetime.strptime(options.stop_time, '%H:%M:%S')
                    b = datetime.now()
                    c = datetime(b.year, b.month, b.day, a.hour, a.minute, a.second)
                    if c < b:
                        c += timedelta(days=1)
                except ValueError:
                    pass
                else:
                    self.programmed_stop = True
                    self.programmed_stop_datetime = c

                try:
                    a = datetime.strptime(options.stop_time, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    pass
                else:
                    self.programmed_stop = True
                    self.programmed_stop_datetime = a

                if not self.programmed_stop is True:
                    print 'Error: allowed stop-time formats are:' \
                          '\n"HH:MM:SS" and "YY-mm-dd HH:MM:SS"'
                    quit()
                else:
                    print 'Automated Stop activated: {0:s}'.format(str(self.programmed_stop_datetime))
                
            # output directory
            if options.output_dir:
                if os.path.exists(options.output_dir):
                    self.output_dir = os.path.realpath(options.output_dir)
                    print self.output_dir
                    print 'Output Directory: {0:s}'.format(self.output_dir)
                else:
                    print 'Error: output directory does not exist'
                    quit()

            # instant start and idle_screen
            self.instant_start = options.instant_start
            if self.instant_start:
                print 'Instant Start: ON'
            self.idle_screen = options.idle_screen
            if self.idle_screen:
                print 'Video Display OFF'
        print 

        # #######################################
        # LAYOUTS
        self.main = QtGui.QWidget()
        self.setCentralWidget(self.main)

        self.main_layout = QtGui.QVBoxLayout()
        self.main.setLayout(self.main_layout)

        self.top_layout = QtGui.QHBoxLayout()
        self.bottom_layout = QtGui.QHBoxLayout()
        self.bottom_info_layout = QtGui.QHBoxLayout()

        self.main_layout.addLayout(self.top_layout)
        self.main_layout.addLayout(self.bottom_layout)
        self.main_layout.addLayout(self.bottom_info_layout)

        # #######################################
        # POPULATE TOP LAYOUT
        self.videos = QtGui.QTabWidget()
        self.videos.setMinimumWidth(min_tab_width)
        self.videos.setMaximumWidth(max_tab_width)
        self.video_recordings = None
        self.video_tabs = {}

        self.metadata = QtGui.QTabWidget()
        self.metadata.setMinimumWidth(min_tab_width)
        self.metadata.setMaximumWidth(max_tab_width)

        self.top_layout.addWidget(self.videos)
        self.top_layout.addWidget(self.metadata)

        # #######################################
        # POPULATE TAB
        default_template_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'templates', default_xml_template)
        self.populate_metadata_tab(default_template_path)
        self.populate_video_tabs()

        # #######################################
        # POPULATE BOTTOM LAYOUT
        self.button_record = QtGui.QPushButton('Start Recording')
        self.button_stop = QtGui.QPushButton('Stop')
        self.button_cancel = QtGui.QPushButton('Cancel')
        self.button_tag = QtGui.QPushButton('&Tag')
        self.button_idle = QtGui.QPushButton('Idle Screen')

        self.button_stop.setDisabled(True)
        self.button_cancel.setDisabled(True)
        self.button_tag.setDisabled(True)

        self.button_record.setMinimumHeight(50)
        self.button_stop.setMinimumHeight(50)
        self.button_cancel.setMinimumHeight(50)
        self.button_tag.setMinimumHeight(50)
        self.button_idle.setMinimumHeight(50)

        self.bottom_layout.addWidget(self.button_record)
        self.bottom_layout.addWidget(self.button_stop)
        self.bottom_layout.addWidget(self.button_cancel)
        self.bottom_layout.addWidget(self.button_tag)
        self.bottom_layout.addWidget(self.button_idle)

        self.label_time = QtGui.QLabel('', self)
        font = self.label_time.font()
        font.setPointSize(18)
        self.label_time.setFont(font)

        self.bottom_info_layout.addStretch(0)
        self.bottom_info_layout.addWidget(self.label_time)
        self.bottom_info_layout.addStretch(0)

        # #######################################
        self.create_menu_bar()

        # #######################################
        # CONNECTIONS
        # These are necessary to connect GUI elements and instances in various threads.
        # Signals and slots can easily be custom-crafted to meet the needs. Data can be sent easily, too.

        # connect buttons
        self.connect(self.button_cancel, QtCore.SIGNAL('clicked()'), self.clicked_cancel)
        self.connect(self.button_record, QtCore.SIGNAL('clicked()'), self.clicked_record)
        self.connect(self.button_stop, QtCore.SIGNAL('clicked()'), self.clicked_stop)
        self.connect(self.button_tag, QtCore.SIGNAL('clicked()'), self.clicked_tag)
        self.connect(self.button_idle, QtCore.SIGNAL('clicked()'), self.clicked_idle)

        # create keyboard shortcuts
        self.create_actions()

        # instant start
        if self.instant_start:
            self.clicked_record()

        # start cameras
        for cam_name, cam in self.cameras.items():
            self.connect(self, QtCore.SIGNAL('start_capture'), cam.start_capture)
            self.connect(self, QtCore.SIGNAL('stop_capture'), cam.stop_capture)
            self.camera_threads[cam_name].start()
        self.emit(QtCore.SIGNAL("start_capture"))

    def create_menu_bar(self):
        self.statusBar()

        exit_action = QtGui.QAction(QtGui.QIcon('exit.png'), '&Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setStatusTip('Exit application')
        exit_action.triggered.connect(QtGui.qApp.quit)

        template_select_action = QtGui.QAction('&Select template', self)
        template_select_action.setStatusTip('Select metadata template')
        template_select_action.triggered.connect(self.select_template)

        about_action = QtGui.QAction('&About', self)
        about_action.setStatusTip('About videoRecorder')
        about_action.triggered.connect(self.show_about)

        cam_config_action = QtGui.QAction('&Camera config', self)
        cam_config_action.setStatusTip('Set camera aliases')
        cam_config_action.triggered.connect(self.cam_aliases)

        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu('&File')
        file_menu.addAction(exit_action)
        config_menu = menu_bar.addMenu('&Configuration')
        config_menu.addAction(template_select_action)
        config_menu.addAction(cam_config_action)
        help_menu = menu_bar.addMenu('&Help')
        help_menu.addAction(about_action)

        # #######################################
        # #######################################

    def select_template(self):
        path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'templates')
        if not os.path.isdir(path):
            path = os.path.abspath('.')

        file_name = QtGui.QFileDialog.getOpenFileName(self, 'Open template', path, "XML files (*.xml *.odml)")
        if file_name:
            self.populate_metadata_tab(file_name)

    def cam_aliases(self):
        pass

    def show_about(self):
        #TODO implement this method which shows a new window
        print 'show about dialog'
        pass

    def populate_metadata_tab(self, template):
        try:
            temp = odml.tools.xmlparser.load(template)
        except:
            print('failed to load metadata template! {0}'.format(template))
            return

        self.metadata_tabs.clear()
        self.metadata.clear()
        for s in temp.sections:
            self.metadata_tabs[s.type] = MetadataTab(s,self.metadata)

    def populate_video_tabs(self):
        # find and initialize cameras
        tmp = [cam for cam in [Camera(i) for i in camera_device_search_range] if cam.is_working()]

        # put cameras into dictionary
        self.cameras = dict()
        for j, cam in enumerate(tmp):
            cam.name = camera_name_format % j
            cam.color = self.color
            self.cameras[cam.name] = cam

        if len(self.cameras) > 0:

            # create tabs for cameras
            for cam_name, cam in self.cameras.items():
                self.video_tabs[cam_name] = VideoCanvas(parent=self)
                self.videos.addTab(self.video_tabs[cam_name], cam_name)
                self.video_tabs[cam_name].setLayout(QtGui.QHBoxLayout())

            # create threads for cameras
            self.camera_threads = dict()
            for cam_name, cam in self.cameras.items():
                self.camera_threads[cam_name] = QtCore.QThread(parent=self)
                cam.moveToThread(self.camera_threads[cam_name])
                self.connect(cam, QtCore.SIGNAL("NewFrame(PyQt_PyObject)"), self.update_canvas)
                self.connect(self, QtCore.SIGNAL("start_recordings ( PyQt_PyObject ) "), cam.create_and_start_new_recording)
                self.connect(self, QtCore.SIGNAL("stop_recordings"), cam.stop_recording)

        else:
            self.videos.addTab(QtGui.QWidget(), "No camera found")

    def create_and_start_new_videorecordings(self):
        # @jan: could choose potentially from PIM1, MJPG, MP42, DIV3, DIVX, U263, I263, FLV1
        # CV_FOURCC('P','I','M','1')    = MPEG-1 codec
        
        if self.trial_counter == 0:
            self.check_data_dir()

        trial_name = '{0:s}/trial_{1:04d}'.format(self.data_dir, self.trial_counter)
        self.tags = list()

        # emit signal to create and start new video-recordings
        self.emit(QtCore.SIGNAL("start_recordings ( PyQt_PyObject ) "), trial_name )

        # drop timestamp for start or recording
        trial_info_filename = '{0:s}/trial_{1:04d}_info.dat'.format(self.data_dir, self.trial_counter)
        self.starttime = datetime.now()
        timestamp = self.starttime.strftime("%Y-%m-%d  %H:%M:%S")
        with open(trial_info_filename, 'w') as f:
            f.write('start-time: '+timestamp+'\n')

        # display start time
        time_label = 'start-time: {0:s}   ---  running: {1:s}'.format(timestamp, str(datetime.now()-self.starttime)[:-7])
        self.label_time.setText(time_label)

        self.is_recording = True

    def check_data_dir(self):
        today = date.today()
        today_str = today.isoformat()
        self.data_dir = os.path.join(self.output_dir, today_str)
        try:
            os.mkdir(self.data_dir)
            self.trial_counter = 0
        except:
            tmp = os.listdir(self.data_dir)
            if len(tmp) > 0:
                self.trial_counter = np.amax([int(e.split('_')[1]) for e in [ee.split('.')[0] for ee in tmp]])+1

    def stop_all_recordings(self):
        # drop timestamp for stop
        trial_info_filename = '{0:s}/trial_{1:04d}_info.dat'.format(self.data_dir, self.trial_counter)
        with open(trial_info_filename, 'a') as f:
            timestamp = datetime.now().strftime("stop-time: %Y-%m-%d  %H:%M:%S:%f")[:-3]
            f.write(timestamp+'\n')

        # emit stop signal
        self.emit(QtCore.SIGNAL("stop_recordings"))

        self.is_recording = False

        self.label_time.setText('')
        self.starttime = None

    def start_stop(self):
        if self.is_recording:
            self.clicked_stop()
        else:
            self.clicked_record()

    def clicked_record(self):
        self.record_timestamp = str(datetime.now()).split('.')[0]
        self.create_and_start_new_videorecordings()
        self.button_record.setDisabled(True)
        self.button_cancel.setEnabled(True)
        self.button_tag.setEnabled(True)
        self.button_stop.setDisabled(False)

    def clicked_cancel(self):
        self.clicked_stop()
        trial_name = 'trial_{0:04d}'.format(self.trial_counter-1)
        map(os.remove, glob.glob(self.data_dir+'/'+trial_name+'*'))
        self.check_data_dir()
        self.button_cancel.setEnabled(False)
        self.button_tag.setEnabled(False)

    def clicked_stop(self):
        self.stop_all_recordings()
        self.button_record.setDisabled(False)
        self.button_stop.setDisabled(True)
        self.button_cancel.setDisabled(True)
        self.button_tag.setDisabled(True)
        # self.save_metadata()
        self.trial_counter += 1

    def clicked_tag(self):
        ts = str(datetime.now()).split('.')[0]
        text, ok = QtGui.QInputDialog.getText(self, 'Tag data with Event', 'Enter tag comment:')
        if ok:
            tag_name = 'event_{0:02d}'.format(len(self.tags)+1)
            e = odml.Section(tag_name, 'event')
            e.append(odml.Property('timestamp', ts, dtype='datetime'))
            e.append(odml.Property('comment', text, dtype='string'))
            self.event_list.append(e)

    def clicked_idle(self):
        if self.idle_screen:
            self.idle_screen = False
        else:
            self.idle_screen = True
            # set idle screen
            for cam_name, cam in self.cameras.items():
                canvas_h = self.video_tabs[cam_name].canvas_h 
                canvas_w = self.video_tabs[cam_name].canvas_w
                img = image.fromarray(np.zeros((canvas_h, canvas_w))).convert('RGB')
                self.video_tabs[cam_name].setImage(QtGui.QPixmap.fromImage(iqt.ImageQt(img)))

    def save_metadata(self):
        trial_name = 'trial_{0:04d}'.format(self.trial_counter)
        file_list = [f for f in os.listdir(self.data_dir) if f.startswith(trial_name)]
        # create a document
        doc = odml.Document()
        # create dataset section
        ds = odml.Section('datasets', 'dataset')
        p = odml.Property('files', None)
        ds.append(p)
        for f in file_list:
            p.append('{0:s}/{1:s}'.format(self.data_dir, f))
        doc.append(ds)

        for t in self.metadata_tabs.values():
            m = t.metadata()
            if m.type == 'recording':
                m.append(odml.Property('StartTime', self.record_timestamp))
            doc.append(m)

        for cam_name, cam in self.cameras.items():
            s = odml.Section(cam_name,'hardware/camera')
            s.append(odml.Property('Framerate', frames_per_second, dtype='int', unit='Hz'))
            for p, v in cam.get_properties().items():
                prop = odml.Property(p, v)
                s.append(prop)
            doc.append(s)
        doc.append(self.event_list)

        from odml.tools.xmlparser import XMLWriter
        writer = XMLWriter(doc)
        writer.write_file('{0}/{1}.xml'.format(self.data_dir, trial_name))

    def update_canvas(self, data):
        # check for programmed stop-time
        if self.programmed_stop \
           and self.programmed_stop_datetime < datetime.now():
            self.stop_all_recordings()
            # wait for recordings to stop
            self.wait(100)
            self.app.exit()

        cam_name = data[0]
        frame = data[1]

        # display frame
        label = self.videos.tabText(self.videos.currentIndex())
        if label == cam_name and not self.idle_screen:
            self.video_tabs[cam_name].setImage(QtGui.QPixmap.fromImage(iqt.ImageQt(image.fromarray(frame))))

        if self.is_recording:
            # display start time
            timestamp = self.starttime.strftime("%Y-%m-%d  %H:%M:%S")
            time_label = 'start-time: {0:s}   ---  running: {1:s}'.format(timestamp, str(datetime.now()-self.starttime)[:-7])
            self.label_time.setText(time_label)

    # ACTIONS
    # Actions can be used to assign keyboard-shortcuts
    # This method is called in the __init__ method to create keyboard shortcuts
    def create_actions(self):
        # EXAMPLE
        # Cancel Recording
        self.action_cancel = QtGui.QAction("Cancel Recording", self)
        self.action_cancel.setShortcut(Qt.Qt.Key_Escape)
        self.connect(self.action_cancel, QtCore.SIGNAL('triggered()'), self.clicked_cancel)
        self.addAction(self.action_cancel)

        # Create a start stop action
        self.action_start_stop = QtGui.QAction('Start, stop recording',self)
        self.action_start_stop.setShortcut(Qt.Qt.CTRL+Qt.Qt.Key_Space)
        self.connect(self.action_start_stop, QtCore.SIGNAL('triggered()'), self.start_stop)
        self.addAction(self.action_start_stop)

        # Create a Tag
        self.action_tag = QtGui.QAction('Tag Movie',self)
        self.action_tag.setShortcut(Qt.Qt.CTRL+Qt.Qt.Key_T)
        self.connect(self.action_tag, QtCore.SIGNAL('triggered()'), self.clicked_tag)
        self.addAction(self.action_tag)

        # Change Tabs
        self.action_change_tab_left = QtGui.QAction("Go one tab to the right", self)
        self.action_change_tab_left.setShortcut(Qt.Qt.CTRL + Qt.Qt.Key_PageDown)
        self.connect(self.action_change_tab_left, QtCore.SIGNAL('triggered()'), self.next_tab)
        self.addAction(self.action_change_tab_left)

        self.action_change_tab_right = QtGui.QAction("Go one tab to the left", self)
        self.action_change_tab_right.setShortcut(Qt.Qt.CTRL + Qt.Qt.Key_PageUp)
        self.connect(self.action_change_tab_right, QtCore.SIGNAL('triggered()'), self.prev_tab)
        self.addAction(self.action_change_tab_right)

    def next_tab(self):
        if self.tab.currentIndex() + 1 < self.tab.count():
            self.tab.setCurrentIndex(self.tab.currentIndex() + 1)
        else:
            self.tab.setCurrentIndex(0)

    def prev_tab(self):
        if self.tab.currentIndex() > 0:
            self.tab.setCurrentIndex(self.tab.currentIndex() - 1)
        else:
            self.tab.setCurrentIndex(self.tab.count() - 1)

    def closeEvent(self, event):
        if self.is_recording:
            self.stop_all_recordings()
        self.emit(QtCore.SIGNAL("stop_capture"))
        for cam_name, thread in self.camera_threads.items():
            thread.quit()
        self.app.exit()

# #######################################
# WORKER CLASSES


# class ControlCenter(QtCore.QObject):
#     """Put your experiment logic here."""
#
#     def __init__(self, parent=None):
#         QtCore.QObject.__init__(self, parent)
#
#
# class DataCollector(QtCore.QObject):
#     """Collect your data in this class."""
#
#     def __init__(self, parent=None):
#         QtCore.QObject.__init__(self, parent)
#
#
# class Storage(QtCore.QObject):
#     """use this class to store your data periodically."""
#
#     def __init__(self, parent=None):
#         QtCore.QObject.__init__(self, parent)

# #######################################

if __name__ == "__main__":

    args = sys.argv
    to_be_parsed = args[1:]

    # define options parser
    parser = OptionParser()
    parser.add_option("-t", "--template", action="store", type="string", dest="template", default='')
    parser.add_option("-k", "--stop_time", action="store", type="string", dest="stop_time", default='')
    parser.add_option("-o", "--output_directory", action="store", type="string", dest="output_dir", default='')
    parser.add_option("-s", "--instant_start", action="store_true", dest="instant_start", default=False)
    parser.add_option("-i", "--idle_screen", action="store_true", dest="idle_screen", default=False)
    (options, args) = parser.parse_args(args)

    # entering the gui app
    qapp = QtGui.QApplication(sys.argv)  # create the main application
    main = Main(qapp, options=options)  # create the mainwindow instance
    main.show()  # show the mainwindow instance
    exit(qapp.exec_())  # start the event-loop: no signals are sent or received without this.
