#    colscript - bqcsv action module to apply a python script to a column 
#
#    Copyright (C) 2017 Winslow Williams 
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

#  The script file must contain two functions:
#
#  def updateHeaders(columns):
#    '''
#      The updateHeaders function is called once at the beginning of the action.

#      "columns" is a list containing the names of the column(s) that will 
#      change.
#      Note that there are three special strings which add columns instead of
#      replacing existing columns:
#        "<" (quotes included) prepends one or more columns to the table
#        ">" (quotes included) appends one or more columns to the table
#        ">[index]<" (quotes included) inserts one or more columns into the 
#        table, [index] is the numeric index where the columns will be inserted.
#
#      The function should return a list containing the new header values. 
#      Note that there may be the same number of headers as passed in, fewer, 
#      or more. If an empty list is returned, it is equivalent to deleting
#      the header value for the specified column(s)
#    '''
#
#  def updateColumn(value):
#    '''
#      The updateColumn function is called once for each row in the table.
#
#      "value" contains a list of the column values for the current row, one 
#      value for each of the column headers passed into the updateHeaders 
#      function.
#
#      The function should return a list of values, one for each of the column
#      headers returned from the updateHeaders function. Note that the exact
#      same number of values must be returned each time the function is called.
#      The number of values must match the number of the header values returned
#      from updateHeaders.
#    '''
#

#  Cases
#    1. One column changing, header can change or not.
#    2. Two or more contiguous columns merging into fewer contiguous columns
#    3. One or more contiguous columns expanding into more contiguous columns
#    4. Two or more noncontiguous columns merging into fewer contiguous columns (replacement takes place at first replaced column)
#    5. One or more noncontiguous columns expanding into more contiguous columns (replacement takes place at first replaced column)
#    6. One or more columns are prepended to the table "<"
#    7. One or more columns are appended to the table ">"
#    8. One or more columns are inserted into the table ">index<"
#    9. One or more columns are deleted from the table (Empty lists are returned from both functions)

import wx
import os
import sys
import os.path
from csvdb import csvmemory
from csvdb import csvfile
from csvdb import csvdb
from actions import utils

H_SPACER = 5
V_SPACER = 5

TITLE = 'ColScript'

EXT_PY = '.py'
EXT_PYC = '.pyc'

PREPEND_STR = '"<"'
APPEND_STR = '">"'
INSERT_PREFIX = '">'
INSERT_SUFFIX = '<"'

class ColScriptDialog(wx.Dialog):

  def __init__(self,parent,table):
    wx.Dialog.__init__(self,parent,-1,TITLE,wx.DefaultPosition,wx.Size(640,-1),wx.DEFAULT_DIALOG_STYLE|wx.RESIZE_BORDER)
    self.table = table
    self.script = None
    self.columns = None

    self.initUI()


  def setPath(self,v):
    '''
    Required
    '''
    self.path = v

  def initUI(self):

    self.SetTitle(TITLE)

    vbox = wx.BoxSizer(wx.VERTICAL)

    vbox.AddSpacer(V_SPACER)

    hbox = wx.BoxSizer(wx.HORIZONTAL)
    hbox.AddSpacer(H_SPACER)
    x = wx.StaticText(self,wx.ID_ANY)
    x.SetLabel("Columns: ")
    hbox.Add(x,1,flag=wx.EXPAND)
    hbox.AddSpacer(H_SPACER)
    self.columns_ctrl = wx.TextCtrl(self,size=(480,-1))
    self.columns_ctrl.SetEditable(True)
    hbox.Add(self.columns_ctrl)
    hbox.AddSpacer(H_SPACER)
    vbox.Add(hbox);

    vbox.AddSpacer(V_SPACER)

    hbox = wx.BoxSizer(wx.HORIZONTAL)
    x = wx.StaticText(self,wx.ID_ANY,label="Script:     ")
    hbox.AddSpacer(H_SPACER)
    hbox.Add(x)
    hbox.AddSpacer(H_SPACER)
    self.script_ctrl = wx.TextCtrl(self,size=(480,-1))
    self.script_ctrl.SetEditable(True)
    hbox.AddSpacer(H_SPACER)
    hbox.Add(self.script_ctrl)
    hbox.AddSpacer(H_SPACER)
    self.script_button = wx.Button(self) 
    self.script_button.SetLabel('...')
    hbox.Add(self.script_button)
    self.script_button.Bind(wx.EVT_BUTTON,self.onSelectScript)
    vbox.Add(hbox);
    hbox.AddSpacer(H_SPACER)
    hbox.AddSpacer(H_SPACER)

    vbox.AddSpacer(V_SPACER)

    hbox = wx.BoxSizer(wx.HORIZONTAL)
    hbox.AddSpacer(H_SPACER)
    self.ok_button = wx.Button(self,wx.ID_OK)
    self.ok_button.Bind(wx.EVT_BUTTON,self.onOK)
    hbox.Add(self.ok_button)
    hbox.AddSpacer(H_SPACER)
    self.cancel_button = wx.Button(self,wx.ID_CANCEL)
    self.cancel_button.Bind(wx.EVT_BUTTON,self.onCancel)
    hbox.Add(self.cancel_button)
    hbox.AddSpacer(H_SPACER)
    vbox.Add(hbox)

    vbox.AddSpacer(V_SPACER)
    vbox.AddSpacer(V_SPACER)

    self.SetSizerAndFit(vbox)


  def onSelectScript(self,event):
    dialog = wx.FileDialog(self,'Script')
    chk = dialog.ShowModal()
    if wx.ID_CANCEL != chk:
        self.script_ctrl.SetValue(dialog.GetPath())

  def onOK(self,event):
    self.columns = list()
    tmp = self.columns_ctrl.GetValue().split(',')
    for x in tmp:
      self.columns.append(x.strip())
    self.script = self.script_ctrl.GetValue()
    self.EndModal(wx.ID_OK)

  def onCancel(self,event):
    self.EndModal(wx.ID_CANCEL)

  def getScript(self):
    return self.script

  def getColumns(self):
    return self.columns

class ChangeInfo(object):

  def __init__(self,header):
    self.index = None
    self.old_header = header
    self.fill_header = None
    self.old_indices = None
    self.new_headers = None

  def setNewHeaders(self,before,after):
    rv = True
    # Check for do nothing case:
    if (before is None) or (0 == len(before)):
      wx.MessageBox("Columns string can't be empty", 'Error', wx.OK | wx.ICON_ERROR)
      return False

    self.new_headers = after
    # Check for special strings first
    if 1 == len(before):
      tst = before[0]
      if tst == PREPEND_STR:
        self.index = 0
      elif tst == APPEND_STR:
        # Flag the index for fixing later
        self.index = len(self.old_header) 
      else:
        if tst.startswith(INSERT_PREFIX) and tst.endswith(INSERT_SUFFIX):
          try:
            self.index = int(tst[2:-2])
          except ValueError as ex: 
            wx.MessageBox('Invalid index string: ' + tst, 'Error', wx.OK | wx.ICON_ERROR)
            rv = False

    # Check for previous error
    if rv:
      # If we found a special string, self.index is set and we use the old 
      # header for the fill header
      if self.index:
        self.fill_header = self.old_header
      # Otherwise, we have to cut out the "before" columns to create our fill 
      # header. Set self.index to be the first cut header
      else:
        idx = 0
        found = False
        self.old_indices = list()
        self.fill_header = list()
        for x in self.old_header:
          if x not in before:
            self.fill_header.append(x)
          else:
            if False == found:
              self.fill_header.append(x)
              self.index = idx
              found = True
            self.old_indices.append(idx)
          idx += 1
    return rv
    
  def getHeader(self):
    rv = list()
    idx = 0
    for v in self.fill_header:
      if idx == self.index:
        for x in self.new_headers:
          rv.append(x)
      else:
        rv.append(v)
      idx += 1
    if idx == self.index:
      for x in self.new_headers:
        rv.append(x)
    return rv

def fixupSysPath(new_path):
    if False == (new_path in sys.path):
      sys.path.append(new_path) 

def loadScript(path):
  rv = None
  try:
    if path.endswith(EXT_PY):
      path = path[:-3] 
    elif path.endswith(EXT_PYC):
      path = path[:-4] 

    (d,f) = os.path.split(path) 
    fixupSysPath(d)
    rv = __import__(f,fromlist = ["*"])
    if None is not rv:
      if False == hasattr(rv,'updateHeaders'):
        wx.MessageBox('Script is missing the updateHeaders function', 'Error', wx.OK | wx.ICON_ERROR)
        rv = None
      elif False == hasattr(rv,'updateColumn'):
        wx.MessageBox('Script is missing the updateColumn function', 'Error', wx.OK | wx.ICON_ERROR)
        rv = None
  except ImportError as ex:
    wx.MessageBox('Error importing script (' + path + '): ' + ex.message, 'Error', wx.OK | wx.ICON_INFORMATION)
    rv = None
  return rv 

def doColScript(table,script,cols,memdb):
  rv = False
  mod = loadScript(script)
  if None is not mod:
    table.reset()
    new_headers = mod.updateHeaders(cols) 
    ci = ChangeInfo(table.getHeader()) 
    rv = ci.setNewHeaders(cols,new_headers)
    if rv:
      memdb.setHeader(ci.getHeader())
      for row in table.getIter():
        new_row = list()
        idx = 0
        old_values = list()
        if ci.old_indices is not None:
          for old_index in ci.old_indices:
            old_values.append(row[old_index])
        for v in row:
          if idx == ci.index:
            new_values = mod.updateColumn(old_values) 
            for new_value in new_values:
              new_row.append(new_value)
          else:
            new_row.append(v)
          idx += 1
        # Take care of the special "append" case
        if idx == ci.index:
          new_values = mod.updateColumn(old_values) 
          for new_value in new_values:
            new_row.append(new_value)
        memdb.appendRow(new_row)
  return rv

class ColScriptPlugin(object):

  def __init__(self,parent_frame):
    self.path = None
    self.parent_frame = parent_frame
 
  def getLabel(self):
    '''
    Required
    '''
    return 'Column Script'

  def getDescription(self):
    '''
    Required
    '''
    return 'Modify columns in open file'

  def setPath(self,v):
    self.path = v

  def doAction(self,table):
    '''
    Required
    '''
    if None is table:
      wx.MessageBox('Missing table', 'Info', wx.OK | wx.ICON_INFORMATION)
      return
    dialog = ColScriptDialog(self.parent_frame,table)
    dialog.SetSize((400,-1))
    chk = dialog.ShowModal()
    if wx.ID_OK == chk:
      script = dialog.getScript()
      columns = dialog.getColumns()
      memdb = csvmemory.MemoryWriter()
   
      chk = doColScript(table,script,columns,memdb)
      if chk:
        path = utils.getTempFilename()
        memdb.save(path)
        self.parent_frame.addPage(path,delete_on_exit=True)

def getPlugin(parent_frame):
  return ColScriptPlugin(parent_frame)


