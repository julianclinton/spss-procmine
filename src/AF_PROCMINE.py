#/***********************************************************************
# * Licensed Materials - Property of Analytical Factory Ltd.
# *
# * (C) Copyright Analytical Factory Ltd. 2026. All Rights Reserved.
# *
# ************************************************************************/

__author__ = "Analytical Factory, JJC"
__version__ = "0.0.1"

helptext="""The AF PROCMINE command requires the Python Integration Plug-in.

AF PROCMINE PROCESS_ID ACTIVITY_NAME START_DATE END_DATE
  [/SAVE MODELFILE=filespec]
  [/OUTFILE LOGFILE=filespec LOGACCESSMODE={OVERWRITE* | APPEND}]

AF PROCMINE /HELP prints this information and does nothing else.

Example:
AF PROCMINE PROCESS_ID="Case-id" ACTIVITY_NAME="Activity" START_DATE="Start-Date" END_DATE="End-Date" 
  /SAVE MODELFILE="process_model.json"
  /OUTFILE LOGFILE="process_log.txt" LOGACCESSMODE=APPEND

"""
import spss, spssaux
from spssaux import u
from extension import Template, Syntax, checkrequiredparams, processcmd
import sys, inspect, logging, json, tempfile, os, csv, codecs, gettext, os.path, textwrap, time, locale

def new_activity(activity_name):
    """Create a new activity dictionary"""
    activity = { "activity_name": activity_name, "from_activities": {}, "to_activities": {}}
    return activity

def processmine(process_id, activity_name, start_date, end_date="", outmodelfile=None,
                logfile=None, logaccessmode="overwrite"):
    """Run Process mining."""
    global logger
    logger = Logger(logfile=logfile, accessmode=logaccessmode)

    activedsname = spss.ActiveDataset()
    if activedsname is None:
        raise ValueError(("""The required active dataset name was not specified"""))

    logger.info("Running process mining with process_id={process_id}".format(process_id=process_id))

    process_model = { "activities": {} }
    fields = [process_id, activity_name, start_date, end_date]

    varDict = spssaux.VariableDict(fields)
    varIndices = [varDict[var].index for var in fields]

    #cur=spss.Cursor(accessType='r', cvtDates='ALL')
    cur=spss.Cursor(var=varIndices, accessType='r')
    for i in range(spss.GetCaseCount()):
        case = cur.fetchone()
        # For now assume process_id and activity_name are strings, start_date and end_date are dates
        process_id_value = case[0].strip()
        activity_name_value = case[1].strip()
        start_date_value = case[2]
        end_date_value = case[3] if len(case) > 3 else None
    cur.close()

    # data = spssdata.Spssdata(fields, names=True)
    # case = None
    # for row in data:
    #     logger.info("Row: %s" % str(row))
    #     case = row
    # data.CClose()

    spss.StartProcedure("Output")
    table = spss.BasePivotTable("Sample Table","OMS subtype")
    table.SimplePivotTable(rowlabels = ["1","2"],
        collabels = ["A","B"],
        cells = ["1A","1B","2A","2B"])    

    table = spss.BasePivotTable("Info ","Info")
    table.Append(spss.Dimension.Place.row,"rowdim",hideLabels=True)
    rowLabel = spss.CellText.String("1")
    table[(rowLabel,)] = spss.CellText.String("""First line of table content
    Version 1""")

    textBlock1 = spss.TextBlock("1. Variable information", str(varDict))
    textBlock2 = spss.TextBlock("2. Last row", str(case))

    spss.EndProcedure()

def Run(args):
    """Execute the PROCMINE command"""

    args = args[list(args.keys())[0]]

    oobj = Syntax([
        Template("PROCESS_ID", subc="", var="process_id", ktype="varname"),
        Template("ACTIVITY_NAME", subc="", var="activity_name", ktype="varname"),
        Template("START_DATE", subc="", var="start_date", ktype="varname"),
        Template("END_DATE", subc="", var="end_date", ktype="varname"),
        Template("MODELFILE", subc="SAVE", ktype="literal", var="outmodelfile"),
        Template("LOGFILE", subc="OUTFILE", var="logfile", ktype="literal"),
        Template("LOGACCESSMODE", subc="OUTFILE", var="logaccessmode", ktype="str", vallist=("overwrite", "append")),
    ])

    if "HELP" in args:
        #print helptext
        helper()
    else:
        processcmd(oobj, args, processmine, vardict=spssaux.VariableDict())

class Logger(object):
    """Manage logging"""
    def __init__(self, logfile, accessmode):
        """Enable logging
        
        logfile is the path for the log file or None
        accessmode is "overwrite" or "append" """

        self.logfile = logfile
        if logfile is not None:
            filemode = accessmode == "overwrite" and "w" or "a"
            logging.basicConfig(filename=logfile, level=logging.INFO, filemode=filemode,
                format="%(asctime)s: %(message)s", datefmt="%H:%M:%S")
            logging.info("Run started: %s" % time.asctime())
            self.starttime = time.time()

    def info(self, message):
        """Add message to the log if logging"""

        if self.logfile:
            logging.info(message)

    def done(self):
        if self.logfile:
            logging.info("Run ended.  Elapsed time (minutes) = %.3f", (time.time() - self.starttime)/60)
            logging.shutdown()


def helper(): 
    import webbrowser, os.path
    path = os.path.splitext(__file__)[0]
    helpspec = "file://" + path + os.path.sep + "markdown.html"
    browser = webbrowser.get()
    if not browser.open_new(helpspec):
        print("Help file not found:" + helpspec)

try:
    from extension import helper
except:
    pass
