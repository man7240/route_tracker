import os
import json
import math
import time
from jnius import autoclass, PythonJavaClass, java_method

Service = autoclass('org.kivy.android.PythonService')
CTX = Service.mService
FILES = CTX.getExternalFilesDir(None).getAbsolutePath()
LIVE = os.path.join(FILES, 'track_live.json')

Context = autoclass('android.content.Context')
PowerManager = autoclass('android.os.PowerManager')
HandlerThread = autoclass('android.os.HandlerThread')

def hav(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1 = math.radians(lat1); p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1); dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

committed = []
pend = None
head = None
lm = None
last_poll_time = -1

class LocListener(PythonJavaClass):
    __javainterfaces__ = ['android/location/LocationListener']
    def __init__(self):
        super().__init__()
    @java_method('(Landroid/location/Location;)V')
    def onLocationChanged(self, location):
        try:
            handle(location)
        except Exception:
            pass
    @java_method('(Ljava/lang/String;)V')
    def onProviderEnabled(self, provider):
        pass
    @java_method('(Ljava/lang/String;)V')
    def onProviderDisabled(self, provider):
        pass
    @java_method('(Ljava/lang/String;ILandroid/os/Bundle;)V')
    def onStatusChanged(self, provider, status, extras):
        pass

def handle(loc):
    global pend, head
    acc = float(loc.getAccuracy())
    if acc > 50.0:
        return
    fix = {
        'lat': float(loc.getLatitude()),
        'lon': float(loc.getLongitude()),
        'altitude': float(loc.getAltitude()),
        'speed': float(loc.getSpeed()),
        'bearing': float(loc.getBearing()),
        'accuracy': acc,
        'time': float(loc.getTime()) / 1000.0,
    }
    head = fix
    if not committed:
        if pend is None:
            pend = fix
            write()
            return
        if hav(pend['lat'], pend['lon'], fix['lat'], fix['lon']) <= 10.0:
            committed.append(pend)
        pend = fix
        write()
        return
    if pend is None:
        pend = fix
        write()
        return
    d_move = hav(committed[-1]['lat'], committed[-1]['lon'], pend['lat'], pend['lon'])
    d_conf = hav(pend['lat'], pend['lon'], fix['lat'], fix['lon'])
    if d_move >= 5.0 and d_conf <= 12.0:
        committed.append(pend)
        pend = fix
    elif d_conf > 12.0:
        pend = fix
    write()

def write():
    tmp = LIVE + '.tmp'
    pts = list(committed)
    if pend is not None:
        pts.append(pend)
    with open(tmp, 'w') as f:
        json.dump({'running': True, 'points': pts, 'head': head}, f)
    os.replace(tmp, LIVE)

def poll_last_known():
    # В фоне система почти не шлёт колбэки — поэтому КАЖДЫЕ 2 СЕКУНДЫ
    # сами активно читаем getLastKnownLocation и пишем точку в файл.
    global last_poll_time
    if lm is None:
        return
    best = None
    for prov in ('gps', 'network'):
        try:
            loc = lm.getLastKnownLocation(prov)
        except Exception:
            loc = None
        if loc is None:
            continue
        if best is None or loc.getTime() > best.getTime():
            best = loc
    if best is None:
        return
    t = int(best.getTime())
    if t == last_poll_time:
        return   # нового фикса с прошлого опроса нет
    last_poll_time = t
    handle(best)

def main():
    global lm
    pm = CTX.getSystemService(Context.POWER_SERVICE)
    wl = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, 'routetracker:track')
    wl.setReferenceCounted(False)
    wl.acquire()
    lm = CTX.getSystemService(Context.LOCATION_SERVICE)
    ht = HandlerThread('gps_worker')
    ht.start()
    listener = LocListener()
    for prov in ('gps', 'network'):
        try:
            if lm.isProviderEnabled(prov):
                lm.requestLocationUpdates(prov, 1000, 0.0, listener, ht.getLooper())
        except Exception:
            pass
    write()
    while True:
        time.sleep(2)
        try:
            poll_last_known()
        except Exception:
            pass

main()
