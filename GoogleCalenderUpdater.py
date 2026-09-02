import icalendar
import requests
from requests.auth import HTTPBasicAuth
import re
import ast
# Google calender API imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import datetime
import os.path
SCOPES = ["https://www.googleapis.com/auth/calendar"]
deltaCutoff = 5

def getConfig():
    f = open("config.txt","rt")
    config = f.readlines()
    x = ast.literal_eval(config[0])
    global colours 
    global downloadURL
    global uniTimetableCalendarId
    global username
    global password
    global deltaCutoff
    colours = ast.literal_eval(config[1])
    downloadURL = x["downloadURL"] 
    uniTimetableCalendarId = x["uniTimetableCalendarId"]
    username = x["username"]
    password = x["password"]
    deltaCutoff = x["deltaCutoff"]
    f.close()
def logIt(Message, type):
    f = open("logcal.txt","at")
    f.write("{} [{}] {}\n".format(datetime.datetime.now(),type,Message))
    f.close()
    print(Message)
def getUofGTimetable():
    newCalender = requests.get(downloadURL,auth=HTTPBasicAuth(username,password))
    return newCalender.text

def getEvents(minTime):
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

def addEvent(title,description,location,start,end):
    logIt("New event added \n Title = {},\n Description = {},\n Location = {},\n Start = {},\n End = {}".format(title,description,location,start,end),"INFO")
    colourId = 1
    for colour in colours:
        if re.search("(?i){}".format(colour),title):
            colourId = colours[colour]
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
        "colorId": colourId
    }
    # Add event addition to batch request
    batch.add(service.events().insert(calendarId=uniTimetableCalendarId, body=eventBody))


def deleteEvent(id):
    x = [y for y in EventsToBeRemoved if y["id"]==id]
    x = x[0]
    logIt("Event Deleted \n Id = {}, \n Title = {},\n Description = {},\n Location = {},\n Start = {},\n End = {}".format(id, x["summary"],x["description"],x["location"],x["start"]["dateTime"],x["end"]["dateTime"]),"INFO")
    batch.add(service.events().delete(calendarId=uniTimetableCalendarId, eventId=id))

def editEvent(newTitle,newDescription,newLocation,newStart,newEnd,id):
    logIt("Event edited \n id = {}, \n Title = {},\n Description = {},\n Location = {},\n Start = {},\n End = {}".format(id, newTitle,newDescription,newLocation,newStart,newEnd),"INFO")
    colourId = 1
    for colour in colours:
        if re.search("(?i){}".format(colour),newTitle):
            colourId = colours[colour]
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
    batch.add(service.events().update(calendarId=uniTimetableCalendarId, eventId=id, body=eventBody))

def setupCreds(): # Setup all da crededitial mess 
    global creds 
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json",SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json","w") as token:
            token.write(creds.to_json())

def batchCallback(request_id, response, exception):
    if exception:
        logIt("Whoops! Request ID {} failed!!: {}".format(request_id,exception),"ERROR")
    else:
        logIt("Fan dabby dosie! Request ID {} went great! Response: {}".format(request_id, response),"INFO")
def delMinTimeICS(events, minTime):
    events = [event for event in events.events if event["DTSTART"].dt > datetime.datetime.fromisoformat(minTime)]
    return events
def compareICSGC(ICS,googlecalendar):
    if ICS["DTSTART"].dt != datetime.datetime.fromisoformat(googlecalendar["start"]["dateTime"]):return False
    elif ICS["DTEND"].dt != datetime.datetime.fromisoformat(googlecalendar["end"]["dateTime"]):return False
    elif ICS["SUMMARY"] != googlecalendar["summary"]:return False
    elif ICS["DESCRIPTION"] != googlecalendar["description"]:return False
    elif ICS["LOCATION"] != googlecalendar["location"]:return False
    else: return True 
def calcDeltaICSGC(ICS,googlecalendar):
    delta = 0
    if ICS["DTSTART"].dt != datetime.datetime.fromisoformat(googlecalendar["start"]["dateTime"]): delta = delta + 1
    if ICS["DTEND"].dt != datetime.datetime.fromisoformat(googlecalendar["end"]["dateTime"]): delta = delta + 1
    if ICS["SUMMARY"] != googlecalendar["summary"]: delta = delta + 1
    if ICS["DESCRIPTION"] != googlecalendar["description"]: delta = delta + 1
    if ICS["LOCATION"] != googlecalendar["location"]: delta = delta + 1
    return delta
if __name__ == "__main__":
    setupCreds()
    getConfig()
    try:
        logIt("Starting...", "INFO")
        service = build("calendar","v3", credentials=creds) # Setup google calender api
        newcalics = getUofGTimetable()
        newcal = icalendar.Calendar.from_ical(newcalics) # get the latest timetable from UofG
        newcal = delMinTimeICS(newcal,"2026-09-20T18:07:16.736812+00:00" )
        oldcal = getEvents("2026-09-20T18:07:16.736812+00:00")
        batch = service.new_batch_http_request(callback=batchCallback)
        EventsToBeAdded = newcal.copy()
        EventsToBeRemoved = oldcal.copy()
        for oldevent in oldcal:
            for newevent in newcal:
                if compareICSGC(newevent,oldevent):
                    EventsToBeAdded.remove(newevent)
                    EventsToBeRemoved.remove(oldevent)
        for removeEvent in EventsToBeRemoved:
            for addedEvent in EventsToBeAdded:
                if calcDeltaICSGC(addedEvent,removeEvent) < deltaCutoff:
                    editEvent(addedEvent["SUMMARY"],addedEvent["DESCRIPTION"],addedEvent["LOCATION"],addedEvent["DTSTART"],addedEvent["DTEND"],removeEvent["id"])
                    EventsToBeAdded.remove(addedEvent)
                    EventsToBeRemoved.remove(removeEvent)
        for event in EventsToBeRemoved:
            deleteEvent(event["id"])
        for event in EventsToBeAdded:
            addEvent(event["SUMMARY"],event["DESCRIPTION"],event["LOCATION"],event["DTSTART"],event["DTEND"])
        batch.execute()
        logIt("Finished!","INFO")
    except HttpError as error:
        logIt("Whoopsy Poopsy, a funny wunny error has occured! {}".format(error),"ERROR")