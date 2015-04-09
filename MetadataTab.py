__author__ = 'Jan Grewe'
try:
    from PyQt4 import QtGui, QtCore, Qt
except Exception, details:
    print 'Unfortunately, your system misses the PyQt4 packages.'
    quit()

import odml
from MetadataEntry import MetadataEntry

class MetadataTab(QtGui.QWidget):
    """This class creates label-and-lineedit-combinations in the tabs and allows for feedback communication."""

    def __init__(self, section, parent):
        QtGui.QWidget.__init__(self, parent)
        self.parent = parent
        self.section = section.clone()
        self.layout = QtGui.QHBoxLayout()
        self.setLayout(self.layout)
        self.page_scroll = Qt.QScrollArea()
        self.layout.addWidget(self.page_scroll)
        self.scroll_contents = QtGui.QWidget()
        self.scroll_layout = QtGui.QVBoxLayout(self.scroll_contents)
        self.parent.addTab(self, self.section.type)
        self.name_entry = None
        self.entries = {}
        self.create_tab()

    def create_tab(self):
        self.entries.clear()
        self.name_entry = None
        self.scroll_contents.setLayout(self.scroll_layout)
        self.page_scroll.setWidgetResizable(False)
        self.populate_tab()
        self.page_scroll.setWidget(self.scroll_contents)

    def populate_tab(self):
        p = odml.Property("name", self.section.name)
        self.name_entry = MetadataEntry(p, self)
        self.scroll_layout.addWidget(self.name_entry)
        for p in self.section.properties:
            entry = MetadataEntry(p, self)
            self.entries[p.name] = entry
            self.scroll_layout.addWidget(entry)

    def metadata(self):
        s = odml.Section(self.name_entry.get_property().value.value, type=self.section.type)
        for e in self.entries.values():
            s.append(e.get_property())
        return s
