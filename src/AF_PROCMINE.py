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

def update_activity_count(activity_dict, activity_name):
    if activity_name not in activity_dict:
        activity_dict[activity_name] = 0
    activity_dict[activity_name] = (
        activity_dict[activity_name] + 1
    )


def processmine(process_id, activity_name, start_date, end_date="", outmodelfile=None,
                logfile=None, logaccessmode="overwrite"):
    """Run Process mining."""
    global logger
    logger = Logger(logfile=logfile, accessmode=logaccessmode)

    activedsname = spss.ActiveDataset()
    if activedsname is None:
        raise ValueError(("""The required active dataset name was not specified"""))

    logger.info("Running process mining with process_id={process_id}".format(process_id=process_id))

    # Traces are sequences of activities for each process_id. Each trace is a list of activities, where each activity is a dictionary with keys "activity_name", "start_date", "end_date", "from_activities" and "to_activities".  The from_activities and to_activities are dictionaries mapping activity names to counts of how many times the transition occurred.
    traces = {}
    process_model = { "activities": {} }
    fields = [process_id, activity_name, start_date, end_date]

    start_activities = {}
    end_activities = {}

    varDict = spssaux.VariableDict(fields)
    varIndices = [varDict[var].index for var in fields]

    #cur=spss.Cursor(accessType='r', cvtDates='ALL')
    cur=spss.Cursor(var=varIndices, accessType='r')
    current_trace = None
    prev_activity = None
    for i in range(spss.GetCaseCount()):
        case = cur.fetchone()
        # For now assume process_id and activity_name are strings, start_date and end_date are dates
        process_id_value = case[0].strip()
        activity_name_value = case[1].strip()
        start_date_value = case[2]
        end_date_value = case[3] if len(case) > 3 else None

        activity = new_activity(activity_name_value)
        activity["start_date"] = start_date_value
        activity["end_date"] = end_date_value

        # If still processing the same trace, add the activity to the current trace. Otherwise, start a new trace.
        if process_id_value == current_trace:
            # Add activity to current trace
            traces[process_id_value].append(activity)
        else:
            # Start a new trace
            current_trace = process_id_value
            traces[process_id_value] = [activity]

            # Count the number of times this activity is a start activity
            update_activity_count(start_activities, activity_name_value)

            # prev_activity was the last activity in the previous trace
            # so count the number of times that activity is an end activity
            if prev_activity is not None:
                update_activity_count(end_activities, prev_activity)                

        prev_activity = activity_name_value

    # Remember to count the last activity in the last trace as an end activity
    if prev_activity is not None:   
        update_activity_count(end_activities, prev_activity)

    # Close the cursor and prepare for output
    cur.close()

    # data = spssdata.Spssdata(fields, names=True)
    # case = None
    # for row in data:
    #     logger.info("Row: %s" % str(row))
    #     case = row
    # data.CClose()

    spss.StartProcedure("Output")

    start_activity_keys = list(start_activities.keys())
    table = spss.BasePivotTable("Start Activities","OMS subtype")
    table.SimplePivotTable(rowlabels = start_activity_keys,
        collabels = ["Count"],
        cells = [start_activities[activity] for activity in start_activity_keys])

    end_activity_keys = list(end_activities.keys())
    table = spss.BasePivotTable("End Activities","OMS subtype")
    table.SimplePivotTable(rowlabels = end_activity_keys,
        collabels = ["Count"],
        cells = [end_activities[activity] for activity in end_activity_keys])

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
