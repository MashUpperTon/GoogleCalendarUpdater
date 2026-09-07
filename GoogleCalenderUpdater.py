import icalendar
import requests
from requests.auth import HTTPBasicAuth
import re
import ast
import os
# Google calender API imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import datetime
import os.path
SCOPES = ["https://www.googleapis.com/auth/calendar"] # What permissions you grant this program from the Google Calendar API
enableBatch = True # Testing varible that disables the batch requests, so that all the program does is output to log
def getConfig(): # Read the config file that contains http url, password and username, gc calendar ID and the "delta cutoff", which determines at what point to edit an event or just delete it and make a new one
    global pwd
    pwd = os.path.dirname(os.path.realpath(__file__)) # Gets the absolute path of the script, so that it can be ran from terminal with no bother
    f = open(os.path.join(pwd, "config.txt"), "rt")
    config = f.readlines()
    x = ast.literal_eval(config[0])
    # defining all the global variables
    global colours 
    global downloadURL
    global uniTimetableCalendarId
    global username
    global password
    global deltaCutoff
    global minTime
    colours = ast.literal_eval(config[1])
    downloadURL = x["downloadURL"] 
    uniTimetableCalendarId = x["uniTimetableCalendarId"]
    username = x["username"]
    password = x["password"]
    deltaCutoff = x["deltaCutoff"]
    minTime = x["minTime"]
    f.close()
def logIt(Message, type): # Log to "logcal.txt" and print to output
    f = open(os.path.join(pwd,"logcal.txt"),"at")
    f.write("{} [{}] {}\n".format(datetime.datetime.now(),type,Message))
    f.close()
    print(Message)
def getUofGTimetable(): # Get ICS file from http server using Http basic authenticain
    newCalender = requests.get(downloadURL,auth=HTTPBasicAuth(username,password))
    return newCalender.text

def getEvents(minTime): # Get google calendar events starting from minTime
    eventResults = (
        service.events()
        .list(
            calendarId=uniTimetableCalendarId,
            timeMin=minTime,
            maxResults=1000,
            singleEvents=True,
            orderBy="startTime"
        )
        .execute()
    )
    events = eventResults.get("items",[])
    return events

def addEvent(title,description,location,start,end): # Add event to google calendar
    colourId = 1 # Default value incase the below fails to find a colour
    for colour in colours:
        if re.search("(?i){}".format(colour),title):
            colourId = colours[colour]
    logIt("New event added \n Title = {},\n Description = {},\n Location = {},\n Start = {},\n End = {}, \n ColorId = {}".format(title,description,location,start,end,colourId),"INFO")
    # Convert werid ical VDDDType object to a python datetime object, then to a RFC 3339 (ISO 8601) formatted string
    start = start.dt.isoformat()
    end = end.dt.isoformat()
    eventBody = {
        "summary": title,
        "description": description,
        "location": location,
        "start": {
            "dateTime": start, 
            "timeZone": "Europe/Belfast" 
        },
        "end": {
            "dateTime": end,
            "timeZone": "Europe/Belfast"
        },
        "colorId": colourId # sorry just wanted to confuse people with british spelling
    }
    # Add event addition to batch request
    if enableBatch: batch.add(service.events().insert(calendarId=uniTimetableCalendarId, body=eventBody))


def deleteEvent(id): # Delete event from google calendar
    x = [y for y in EventsToBeRemoved if y["id"]==id] # List comprehension to find the Event with the correct id, in order to get its properties for logging
    x = x[0]
    logIt("Event Deleted \n Id = {}, \n Title = {},\n Description = {},\n Location = {},\n Start = {},\n End = {}".format(id, x["summary"],x["description"],x["location"],x["start"]["dateTime"],x["end"]["dateTime"]),"INFO")
    if enableBatch: batch.add(service.events().delete(calendarId=uniTimetableCalendarId, eventId=id))

def editEvent(newTitle,newDescription,newLocation,newStart,newEnd,id): # Edit event in google calendar
    x = [y for y in EventsToBeRemoved if y["id"]==id] # List comprehension to find the Event with the correct id, in order to get its properties for logging
    x = x[0]
    colourId = 1 # Default value in case the below can't find a colour
    for colour in colours:
        if re.search("(?i){}".format(colour),newTitle):
            colourId = colours[colour]
    logIt("Event edited \n id = {}, \n Title = {} -> {},\n Description = {} -> {},\n Location = {} -> {},\n Start = {} -> {},\n End = {} -> {}, \n ColorId = {}".format(id, x["summary"],newTitle,x["description"],newDescription,x["location"],newLocation,x["start"]["dateTime"],newStart,x["end"]["dateTime"],newEnd, colourId),"INFO")
    # Convert werid ical VDDDType object to a python datetime object, then to a RFC 3339 (ISO 8601) formatted string
    newStart = newStart.dt.isoformat()
    newEnd = newEnd.dt.isoformat()
    eventBody = {
        "summary": newTitle,
        "description": newDescription,
        "location": newLocation,
        "start": {
            "dateTime": newStart, 
            "timeZone": "Europe/Belfast" 
        },
        "end": {
            "dateTime": newEnd,
            "timeZone": "Europe/Belfast"
        },
        "colorId": colourId,
    }
    # Add event change to batch request
    if enableBatch: batch.add(service.events().update(calendarId=uniTimetableCalendarId, eventId=id, body=eventBody))

def setupCreds(): # Setup all da crededitialis mess, mostly copied from the python quickstart for the google calendar API 
    global creds 
    creds = None
    if os.path.exists(os.path.join(pwd, "token.json")):
        creds = Credentials.from_authorized_user_file(os.path.join(pwd, "token.json"), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(os.path.join(pwd, "credentials.json"), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(os.path.join(pwd, "token.json"), "w") as token:
            token.write(creds.to_json())

def batchCallback(request_id, response, exception): # Function that is called on completion (sucess or error) of http request to google calendar API
    if exception:
        logIt("Whoops! Request ID {} failed!!: {}".format(request_id,exception),"ERROR")
    else:
        logIt("Fan dabby dosie! Request ID {} went great! Response: {}".format(request_id, response),"INFO")
def delMinTimeICS(events, minTime): # Get rid of events preceeding minTime from an ICS data block
    events = [event for event in events.events if event["DTSTART"].dt > datetime.datetime.fromisoformat(minTime)]
    return events
def compareICSGC(ICS,googlecalendar): # compare an ICS and google calendar event to see if they are identical (in terms of title, description, location and start and stop time)
    if ICS["DTSTART"].dt != datetime.datetime.fromisoformat(googlecalendar["start"]["dateTime"]):return False
    elif ICS["DTEND"].dt != datetime.datetime.fromisoformat(googlecalendar["end"]["dateTime"]):return False
    elif ICS["SUMMARY"] != googlecalendar["summary"]:return False
    elif ICS["DESCRIPTION"] != googlecalendar["description"]:return False
    elif ICS["LOCATION"] != googlecalendar["location"]:return False
    else: return True 
def calcDeltaICSGC(ICS,googlecalendar): # compare an ICS and google calendar event and calculate how different they are
    delta = 0
    if ICS["DTSTART"].dt != datetime.datetime.fromisoformat(googlecalendar["start"]["dateTime"]): delta = delta + 1
    if ICS["DTEND"].dt != datetime.datetime.fromisoformat(googlecalendar["end"]["dateTime"]): delta = delta + 1
    if ICS["SUMMARY"] != googlecalendar["summary"]: delta = delta + 1
    if ICS["DESCRIPTION"] != googlecalendar["description"]: delta = delta + 1
    if ICS["LOCATION"] != googlecalendar["location"]: delta = delta + 1
    return delta
if __name__ == "__main__": # Main function
    # Setup variables and google api creds
    getConfig()
    setupCreds()
    try:
        logIt("Starting...", "INFO")
        service = build("calendar","v3", credentials=creds) # Setup google calender api
        newcalics = getUofGTimetable() # get the latest timetable from UofG
        newcal = icalendar.Calendar.from_ical(newcalics) # Convert text ics into iCalendar object
        newcal = delMinTimeICS(newcal, minTime) 
        oldcal = getEvents(minTime) # Last two lines delete events starting before 2026 adademic year 
        if enableBatch: batch = service.new_batch_http_request(callback=batchCallback) # Start batch request
        EventsToBeAdded = newcal.copy()
        EventsToBeRemoved = oldcal.copy()
        # Removes all the events that are identical between the two calendars 
        for oldevent in oldcal:
            for newevent in newcal:
                if compareICSGC(newevent,oldevent):
                    EventsToBeAdded.remove(newevent)
                    EventsToBeRemoved.remove(oldevent)

        # Edits events with differences below deltaCutoff
        for removeEvent in EventsToBeRemoved:
            for addedEvent in EventsToBeAdded:
                if calcDeltaICSGC(addedEvent,removeEvent) < deltaCutoff:
                    editEvent(addedEvent["SUMMARY"],addedEvent["DESCRIPTION"],addedEvent["LOCATION"],addedEvent["DTSTART"],addedEvent["DTEND"],removeEvent["id"])
                    EventsToBeAdded.remove(addedEvent)
                    EventsToBeRemoved.remove(removeEvent)
        # Removes remaining events
        for event in EventsToBeRemoved:
            deleteEvent(event["id"])
        # Adds remaining events
        for event in EventsToBeAdded:
            addEvent(event["SUMMARY"],event["DESCRIPTION"],event["LOCATION"],event["DTSTART"],event["DTEND"])
        if enableBatch: batch.execute() # Execute http batch request
        logIt("Finished!","INFO")
    except HttpError as error: # Called when the http request can't even go through
        logIt("Whoopsy Poopsy, a funny wunny error has occured! {}".format(error),"ERROR")