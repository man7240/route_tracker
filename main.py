import os
import sys
import json
import math
import time
import threading
import traceback
from datetime import datetime, timedelta

print('ROUTE_TRACKER_MAIN_START build=32', flush=True)
BUILD = 32

# ---------------------------------------------------------------------------
# Защита старта: любая ошибка -> красный текст на экране вместо вылета
# ---------------------------------------------------------------------------
def _tb_text():
    return ''.join(traceback.format_exception(*sys.exc_info()))

def _run_error_app(title, text):
    try:
        from kivy.app import App
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.label import Label
        from kivy.uix.boxlayout import BoxLayout
        from kivy.core.window import Window
        Window.clearcolor = (0.06, 0.07, 0.10, 1)
        
        def _mk(t):
            l = Label(text=t, size_hint_y=None, halign='left', valign='top')
            l.bind(width=lambda i, w: setattr(i, 'text_size', (w, None)))
            l.bind(texture_size=lambda i, v: setattr(i, 'height', v[1] + 6))
            return l
            
        class _ErrApp(App):
            def build(self):
                root = BoxLayout(orientation='vertical', padding=10, spacing=10)
                sv = ScrollView()
                sv.add_widget(_mk('[b]%s (build %d)[/b]\n\n%s' % (title, BUILD, text)))
                root.add_widget(sv)
                return root
                
        _ErrApp().run()
    except Exception:
        print('FATAL STARTUP ERROR build=%d:\n%s\n%s' % (BUILD, title, text), flush=True)

def _save_crash(text):
    try:
        from kivy.app import App
        app = App.get_running_app()
        d = app.user_data_dir if app else '.'
    except Exception:
        d = '.'
    try:
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, 'crash.log'), 'a', encoding='utf-8') as f:
            f.write('--- startup crash build=%d ---\n%s\n' % (BUILD, text))
    except Exception:
        pass

# ---------------------------------------------------------------------------
try:
    from kivy.app import App
    from kivy.core.window import Window
    from kivy.uix.screenmanager import ScreenManager, Screen
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.gridlayout import GridLayout
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.label import Label
    from kivy.uix.button import Button
    from kivy.uix.textinput import TextInput
    from kivy.clock import Clock
    from kivy.utils import platform
    from kivy.logger import Logger

    Window.clearcolor = (0.06, 0.07, 0.10, 1)

    def _excepthook(exc_type, exc_value, exc_tb):
        try:
            txt = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
            try:
                d = App.get_running_app().user_data_dir if App.get_running_app() else '.'
            except Exception:
                d = '.'
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, 'crash.log'), 'a', encoding='utf-8') as f:
                f.write('--- excepthook ---\n' + txt + '\n')
        except Exception:
            pass
        try:
            sys.__excepthook__(exc_type, exc_value, exc_tb)
        except Exception:
            pass

    sys.excepthook = _excepthook

    MAPVIEW_OK = False
    MapView = None
    MapMarker = None
    MapLayer = None

    try:
        from kivy_garden.mapview import MapView, MapMarker, MapLayer
        MAPVIEW_OK = True
    except Exception as e:
        Logger.error('MapView import error: %s' % e)

    # ----------------------- гео-помощники -----------------------
    def _haversine_m(lat1, lon1, lat2, lon2):
        R = 6371000.0
        p1 = math.radians(float(lat1)); p2 = math.radians(float(lat2))
        dp = math.radians(float(lat2) - float(lat1))
        dl = math.radians(float(lon2) - float(lon1))
        a = (math.sin(dp / 2.0) ** 2 +
             math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2)
        return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    def _geo_bearing(lat1, lon1, lat2, lon2):
        p1 = math.radians(float(lat1)); p2 = math.radians(float(lat2))
        dl = math.radians(float(lon2) - float(lon1))
        y = math.sin(dl) * math.cos(p2)
        x = (math.cos(p1) * math.sin(p2) -
             math.sin(p1) * math.cos(p2) * math.cos(dl))
        return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0

    # ----------------------- утилиты вёрстки -----------------------
    def _auto_label(text='', font_size='13sp', **kw):
        lbl = Label(text=text, size_hint_y=None, halign='left', valign='top',
                    font_size=font_size, **kw)
        lbl.bind(width=lambda inst, w: setattr(inst, 'text_size', (w, None)))
        lbl.bind(texture_size=lambda inst, v: setattr(inst, 'height', v[1] + 6))
        return lbl

    def _btn(text, bg, height=104, font_size='14sp'):
        b = Button(text=text, size_hint_y=None, height=height,
                   font_size=font_size, bold=True, color=(1, 1, 1, 1),
                   background_color=bg, halign='center', valign='middle')
        b.bind(size=lambda inst, v: setattr(
            inst, 'text_size', (max(10, v[0] - 16), None)))
        return b

    def request_android_permissions():
        if platform != 'android':
            return False
        try:
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.ACCESS_FINE_LOCATION,
                Permission.ACCESS_COARSE_LOCATION,
            ])
            return True
        except Exception as e:
            Logger.error('Android permissions error: %s' % e)
            return False

    def request_ignore_battery_optimizations():
        if platform != 'android':
            return
        try:
            from jnius import autoclass
            Context = autoclass('android.content.Context')
            Settings = autoclass('android.provider.Settings')
            Intent = autoclass('android.content.Intent')
            Uri = autoclass('android.net.Uri')
            PowerManager = autoclass('android.os.PowerManager')
            ctx = autoclass('org.kivy.android.PythonActivity').mActivity
            pm = ctx.getSystemService(Context.POWER_SERVICE)
            if not pm.isIgnoringBatteryOptimizations(ctx.getPackageName()):
                i = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
                i.setData(Uri.parse('package:' + ctx.getPackageName()))
                ctx.startActivity(i)
        except Exception as e:
            Logger.error('battery opt error: %s' % e)

    def safe_filename(name):
        return ''.join(ch if ch.isalnum() or ch in ('-', '_', ' ') else '_'
                       for ch in str(name)).strip() or 'route'

    def fmt_duration(s):
        s = int(s or 0)
        return '%02d:%02d:%02d' % (s // 3600, (s % 3600) // 60, s % 60)

    def fmt_distance(m):
        return '%.2f км' % ((m or 0) / 1000.0)

    def fmt_speed(mps):
        return '%.1f км/ч' % ((mps or 0) * 3.6)

    def make_map(zoom=14):
        if not MAPVIEW_OK:
            return None
        try:
            return MapView(zoom=zoom, lat=55.7522, lon=37.6156)
        except Exception as e:
            Logger.error('MapView create error: %s' % e)
            return None

    # ----------------------- утилиты для маркеров карты -----------------------
    def map_add_marker(mv, marker):
        if mv is None or marker is None:
            return False
        try:
            if hasattr(mv, 'add_marker'):
                mv.add_marker(marker)
                return True
        except Exception as e:
            Logger.error('map.add_marker error: %s' % e)
        try:
            mv.add_widget(marker)
            return True
        except Exception as e:
            Logger.error('map.add_widget(marker) error: %s' % e)
        return False

    def map_remove_marker(mv, marker):
        if mv is None or marker is None:
            return
        try:
            if hasattr(mv, 'remove_marker'):
                mv.remove_marker(marker)
                return
        except Exception as e:
            Logger.error('map.remove_marker error: %s' % e)
        try:
            mv.remove_widget(marker)
        except Exception as e:
            Logger.error('map.remove_widget(marker) error: %s' % e)

    def map_trigger_update(mv):
        if mv is None:
            return
        try:
            if hasattr(mv, 'trigger_update'):
                mv.trigger_update(True)
        except Exception as e:
            Logger.error('map.trigger_update error: %s' % e)
        try:
            mv.canvas.ask_update()
        except Exception:
            pass

    # ----------------------- Слой линии + стрелка курса -----------------------
    if MAPVIEW_OK:
        from kivy.graphics import (Color, Line, PushMatrix, PopMatrix,
                                   Translate, Rotate, Triangle)

        class RouteLineLayer(MapLayer):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.route_points = []
                self._map = None
                self.cur_lat = None
                self.cur_lon = None
                self.cur_bearing = 0.0
                self._ref_lat = None
                self._ref_lon = None
                self._ref_time = 0.0

            def attach(self, mapview):
                self._map = mapview
                self._redraw()
                Clock.schedule_once(lambda dt: self._redraw(), 0)
                Clock.schedule_once(lambda dt: self._redraw(), 0.3)

            def set_points(self, pts):
                self.route_points = pts or []
                self._redraw()
                Clock.schedule_once(lambda dt: self._redraw(), 0)
                Clock.schedule_once(lambda dt: self._redraw(), 0.25)

            def set_current(self, lat, lon, bearing=None):
                now = time.time()
                if lat is None:
                    self.cur_lat = None
                    self.cur_lon = None
                    self.cur_bearing = 0.0
                    self._ref_lat = None
                    self._ref_lon = None
                else:
                    first = self.cur_lat is None
                    self.cur_lat = float(lat)
                    self.cur_lon = float(lon)
                    if bearing is not None and bearing >= 0:
                        b = float(bearing)
                        if first:
                            self.cur_bearing = b
                        else:
                            old = self.cur_bearing
                            diff = (b - old + 180.0) % 360.0 - 180.0
                            self.cur_bearing = (old + diff * 0.6) % 360.0
                        self._ref_lat = float(lat)
                        self._ref_lon = float(lon)
                        self._ref_time = now
                self._redraw()
                Clock.schedule_once(lambda dt: self._redraw(), 0)

            def reposition(self):
                try:
                    super().reposition()
                except Exception:
                    pass
                self._redraw()

            @staticmethod
            def _smooth(pts, iterations=2):
                n = len(pts) // 2
                if n < 3:
                    return pts
                P = [(pts[2 * i], pts[2 * i + 1]) for i in range(n)]
                for _ in range(iterations):
                    Q = [P[0]]
                    for i in range(len(P) - 1):
                        ax, ay = P[i]; bx, by = P[i + 1]
                        Q.append((0.75 * ax + 0.25 * bx, 0.75 * ay + 0.25 * by))
                        Q.append((0.25 * ax + 0.75 * bx, 0.25 * ay + 0.75 * by))
                    Q.append(P[-1])
                    P = Q
                out = []
                for x, y in P:
                    out.extend((x, y))
                return out

            def _xy(self, mv, lat, lon):
                try:
                    return mv.get_window_xy_from(float(lat), float(lon), mv.zoom)
                except TypeError:
                    return mv.get_window_xy_from(float(lat), float(lon))

            def _redraw(self, *a):
                self.canvas.clear()
                mv = self._map
                if mv is None:
                    return
                pts = []
                if len(self.route_points) >= 2:
                    raw = []
                    try:
                        for lat, lon in self.route_points:
                            x, y = self._xy(mv, lat, lon)
                            raw.extend((float(x), float(y)))
                    except Exception as e:
                        Logger.error('RouteLineLayer xy error: %s' % e)
                        raw = []
                    if len(raw) >= 4:
                        pts = self._smooth(raw)
                try:
                    with self.canvas:
                        if pts:
                            Color(1.0, 1.0, 1.0, 0.95)
                            Line(points=pts, width=20, cap='round', joint='round')
                            Color(0.12, 0.47, 0.99, 1.0)
                            Line(points=pts, width=15, cap='round', joint='round')
                        if self.cur_lat is not None:
                            x, y = self._xy(mv, self.cur_lat, self.cur_lon)
                            PushMatrix()
                            Translate(float(x), float(y), 0)
                            Rotate(angle=-self.cur_bearing, axis=(0, 0, 1))
                            Color(1.0, 1.0, 1.0, 0.95)
                            Triangle(points=(-30, -34, 0, 46, 30, -34))
                            Color(0.85, 0.15, 0.15, 1.0)
                            Triangle(points=(-20, -24, 0, 34, 20, -24))
                            Color(1.0, 1.0, 1.0, 0.95)
                            Triangle(points=(-8, -24, 0, -10, 8, -24))
                            PopMatrix()
                except Exception as e:
                    Logger.error('RouteLineLayer draw error: %s' % e)
    else:
        class RouteLineLayer(object):
            def __init__(self, *a, **k):
                pass
            def attach(self, mapview):
                pass
            def set_points(self, pts):
                pass
            def set_current(self, lat, lon, bearing=None):
                pass
            def reposition(self):
                pass

    # ----------------------- GPS: опрос в ГЛАВНОМ потоке -----------------------
    class GPSService:
        def __init__(self):
            self.is_running = False
            self.on_loc = None
            self.on_status = None
            self._lm = None
            self._listener = None
            self._poll_event = None
            self._last_time = -1

        def _android_ctx(self):
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            return PythonActivity.mActivity

        def check_status(self):
            if platform != 'android':
                return 'Не Android'
            try:
                from jnius import autoclass
                Context = autoclass('android.content.Context')
                PackageManager = autoclass('android.content.pm.PackageManager')
                Permission = autoclass('android.Manifest$permission')
                GRANTED = PackageManager.PERMISSION_GRANTED
                ctx = self._android_ctx()
                fine = ctx.checkSelfPermission(Permission.ACCESS_FINE_LOCATION) == GRANTED
                coarse = ctx.checkSelfPermission(Permission.ACCESS_COARSE_LOCATION) == GRANTED
                lm = ctx.getSystemService(Context.LOCATION_SERVICE)
                gps_on = bool(lm.isProviderEnabled('gps'))
                net_on = bool(lm.isProviderEnabled('network'))
                return ('Разрешение: точное=%s приблизит.=%s | '
                        'Провайдеры: GPS=%s NET=%s' % (fine, coarse, gps_on, net_on))
            except Exception as e:
                return 'Статус недоступен (%s)' % e

        def has_permission(self):
            if platform != 'android':
                return True
            try:
                from jnius import autoclass
                PackageManager = autoclass('android.content.pm.PackageManager')
                Permission = autoclass('android.Manifest$permission')
                GRANTED = PackageManager.PERMISSION_GRANTED
                ctx = self._android_ctx()
                fine = ctx.checkSelfPermission(Permission.ACCESS_FINE_LOCATION) == GRANTED
                coarse = ctx.checkSelfPermission(Permission.ACCESS_COARSE_LOCATION) == GRANTED
                return fine or coarse
            except Exception as e:
                Logger.error('has_permission read error (ignore): %s' % e)
                return True

        def configure(self, on_loc, on_status=None):
            self.on_loc = on_loc
            self.on_status = on_status

        def start(self, min_time=1000, min_distance=0):
            if platform != 'android':
                raise RuntimeError('GPS только на Android')
            from jnius import autoclass
            Context = autoclass('android.content.Context')
            Looper = autoclass('android.os.Looper')
            ctx = self._android_ctx()
            self._lm = ctx.getSystemService(Context.LOCATION_SERVICE)
            if not self.has_permission():
                request_android_permissions()
                raise RuntimeError('Нет разрешения на местоположение — выдайте в настройках приложения')
            ListenerCls = _get_listener_cls()
            self._listener = ListenerCls(self._handle_fix, self._handle_provider)
            main_looper = Looper.getMainLooper()
            started = []
            for prov in ('gps', 'network'):
                try:
                    if self._lm.isProviderEnabled(prov):
                        self._lm.requestLocationUpdates(
                            prov, int(min_time), float(min_distance),
                            self._listener, main_looper)
                        started.append(prov)
                except Exception as e:
                    Logger.error('requestLocationUpdates %s error: %s' % (prov, e))
            if not started:
                try:
                    Criteria = autoclass('android.location.Criteria')
                    best = self._lm.getBestProvider(Criteria(), True)
                    if best:
                        self._lm.requestLocationUpdates(
                            best, int(min_time), float(min_distance),
                            self._listener, main_looper)
                        started.append(best)
                except Exception as e:
                    Logger.error('best provider error: %s' % e)
            if not started:
                raise RuntimeError('Нет включённых провайдеров GPS/Network')
            self.is_running = True
            self._last_time = -1
            self._poll_event = Clock.schedule_interval(self._poll, 2.0)
            if self.on_status:
                self.on_status('poll',
                    'Запись + опрос GPS каждые 2с. Провайдеры: %s.' % ', '.join(started))
            return started

        def _poll(self, dt):
            if not self.is_running or self._lm is None:
                return
            best = None
            for prov in ('gps', 'network'):
                try:
                    loc = self._lm.getLastKnownLocation(prov)
                except Exception:
                    loc = None
                if loc is None:
                    continue
                if best is None or loc.getTime() > best.getTime():
                    best = loc
            if best is None:
                return
            t = int(best.getTime())
            if t == self._last_time:
                return
            self._last_time = t
            fix = {
                'lat': float(best.getLatitude()),
                'lon': float(best.getLongitude()),
                'altitude': float(best.getAltitude()),
                'speed': float(best.getSpeed()),
                'bearing': float(best.getBearing()),
                'accuracy': float(best.getAccuracy()),
                'time': t / 1000.0,
            }
            if self.on_loc:
                self.on_loc(fix)

        def stop(self):
            if not self.is_running:
                return
            if self._poll_event is not None:
                try:
                    Clock.unschedule(self._poll_event)
                except Exception:
                    pass
                self._poll_event = None
            try:
                if self._lm is not None and self._listener is not None:
                    self._lm.removeUpdates(self._listener)
            except Exception as e:
                Logger.error('removeUpdates error: %s' % e)
            self.is_running = False

        def _handle_fix(self, fix):
            if self.on_loc:
                self.on_loc(fix)

        def _handle_provider(self, kind, provider):
            if self.on_status:
                self.on_status(kind, provider)

    _LISTENER_CLS = None

    def _get_listener_cls():
        global _LISTENER_CLS
        if _LISTENER_CLS is not None:
            return _LISTENER_CLS
        from jnius import PythonJavaClass, java_method
        class _LocListener(PythonJavaClass):
            __javainterfaces__ = ['android/location/LocationListener']
            def __init__(self, on_fix, on_provider):
                super().__init__()
                self.on_fix = on_fix
                self.on_provider = on_provider
            @java_method('(Landroid/location/Location;)V')
            def onLocationChanged(self, location):
                try:
                    fix = {
                        'lat': float(location.getLatitude()),
                        'lon': float(location.getLongitude()),
                        'altitude': float(location.getAltitude()),
                        'speed': float(location.getSpeed()),
                        'bearing': float(location.getBearing()),
                        'accuracy': float(location.getAccuracy()),
                        'time': float(location.getTime()) / 1000.0,
                    }
                    if self.on_fix:
                        self.on_fix(fix)
                except Exception as e:
                    Logger.error('onLocationChanged error: %s' % e)
            @java_method('(Ljava/lang/String;)V')
            def onProviderEnabled(self, provider):
                if self.on_provider:
                    self.on_provider('enabled', provider)
            @java_method('(Ljava/lang/String;)V')
            def onProviderDisabled(self, provider):
                if self.on_provider:
                    self.on_provider('disabled', provider)
            @java_method('(Ljava/lang/String;ILandroid/os/Bundle;)V')
            def onStatusChanged(self, provider, status, extras):
                pass
        _LISTENER_CLS = _LocListener
        return _LISTENER_CLS

    # ----------------------- База данных -----------------------
    import sqlite3

    class Database:
        def __init__(self, db_path='routes.db'):
            self.conn = sqlite3.connect(db_path)
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS routes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    date TEXT NOT NULL,
                    duration INTEGER,
                    distance REAL,
                    avg_speed REAL,
                    max_speed REAL,
                    total_ascent REAL,
                    total_descent REAL,
                    min_altitude REAL,
                    max_altitude REAL,
                    points_json TEXT NOT NULL
                )
            ''')
            self.conn.commit()

        def save_route(self, name, duration, distance, avg_speed, max_speed,
                       total_ascent, total_descent, min_alt, max_alt, points):
            self.conn.execute('''
                INSERT INTO routes
                (name, date, duration, distance, avg_speed, max_speed,
                 total_ascent, total_descent, min_altitude, max_altitude, points_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, datetime.now().isoformat(), duration, distance,
                  avg_speed, max_speed, total_ascent, total_descent,
                  min_alt, max_alt, json.dumps(points, ensure_ascii=False)))
            self.conn.commit()

        def get_all_routes(self):
            c = self.conn.execute('''
                SELECT id, name, date, distance, duration, avg_speed
                FROM routes ORDER BY date DESC
            ''')
            return c.fetchall()

        def get_route_by_id(self, rid):
            c = self.conn.execute('SELECT * FROM routes WHERE id = ?', (rid,))
            r = c.fetchone()
            if not r:
                return None
            return {
                'id': r[0], 'name': r[1], 'date': r[2], 'duration': r[3],
                'distance': r[4], 'avg_speed': r[5], 'max_speed': r[6],
                'total_ascent': r[7], 'total_descent': r[8],
                'min_altitude': r[9], 'max_altitude': r[10],
                'points': json.loads(r[11]),
            }

        def delete_route(self, rid):
            self.conn.execute('DELETE FROM routes WHERE id = ?', (rid,))
            self.conn.commit()

        def close(self):
            try:
                self.conn.close()
            except Exception:
                pass

    # ----------------------- Расчёты -----------------------
    class RouteCalculator:
        @staticmethod
        def haversine(lat1, lon1, lat2, lon2):
            return _haversine_m(lat1, lon1, lat2, lon2)

        @staticmethod
        def _good(p):
            acc = p.get('accuracy', 0) or 0
            return acc <= 50.0

        @staticmethod
        def distance(points):
            if len(points) < 2:
                return 0.0
            t = 0.0
            for i in range(len(points) - 1):
                if not RouteCalculator._good(points[i]) or not RouteCalculator._good(points[i + 1]):
                    continue
                t += _haversine_m(
                    points[i]['lat'], points[i]['lon'],
                    points[i + 1]['lat'], points[i + 1]['lon'])
            return t

        @staticmethod
        def speeds(points):
            gps_speeds = []
            for p in points:
                s = p.get('speed', 0) or 0
                if s > 0.1:
                    gps_speeds.append(float(s))
            if gps_speeds:
                return sum(gps_speeds) / len(gps_speeds), max(gps_speeds), gps_speeds
            seg = []
            for i in range(len(points) - 1):
                if not RouteCalculator._good(points[i]) or not RouteCalculator._good(points[i + 1]):
                    continue
                d = _haversine_m(
                    points[i]['lat'], points[i]['lon'],
                    points[i + 1]['lat'], points[i + 1]['lon'])
                if d < 3.0:
                    continue
                t1 = float(points[i].get('time', 0) or 0)
                t2 = float(points[i + 1].get('time', 0) or 0)
                dt = t2 - t1
                if dt > 0:
                    seg.append(d / dt)
            if not seg:
                return 0.0, 0.0, seg
            return sum(seg) / len(seg), max(seg), seg

        @staticmethod
        def elevation(points):
            if len(points) < 2:
                return 0.0, 0.0, 0.0, 0.0
            asc = 0.0; desc = 0.0
            mn = float(points[0].get('altitude', 0) or 0); mx = mn
            ref = mn
            for i in range(len(points) - 1):
                a2 = float(points[i + 1].get('altitude', 0) or 0)
                diff = a2 - ref
                if diff > 2.0:
                    asc += diff; ref = a2
                elif diff < -2.0:
                    desc += abs(diff); ref = a2
                if a2 < mn: mn = a2
                if a2 > mx: mx = a2
            return asc, desc, mn, mx

        @staticmethod
        def stats(points):
            if len(points) < 2:
                return {'distance': 0.0, 'avg_speed': 0.0, 'max_speed': 0.0,
                        'total_ascent': 0.0, 'total_descent': 0.0,
                        'min_altitude': 0.0, 'max_altitude': 0.0, 'duration': 0.0}
            dist = RouteCalculator.distance(points)
            t0 = float(points[0].get('time', 0) or 0)
            t1 = float(points[-1].get('time', 0) or 0)
            dur = max(0.0, t1 - t0)
            avg, mxs, _ = RouteCalculator.speeds(points)
            asc, desc, mn, mx = RouteCalculator.elevation(points)
            return {'distance': dist, 'avg_speed': avg, 'max_speed': mxs,
                    'total_ascent': asc, 'total_descent': desc,
                    'min_altitude': mn, 'max_altitude': mx, 'duration': dur}

    # ----------------------- GPX -----------------------
    class GPXExporter:
        @staticmethod
        def export(points, name, out_path):
            import gpxpy
            import gpxpy.gpx
            gpx = gpxpy.gpx.GPX()
            gpx.creator = 'Route Tracker'
            trk = gpxpy.gpx.GPXTrack()
            trk.name = name
            gpx.tracks.append(trk)
            seg = gpxpy.gpx.GPXTrackSegment()
            trk.segments.append(seg)
            for p in points:
                t = None
                if p.get('time'):
                    try:
                        t = datetime.fromtimestamp(float(p['time']))
                    except Exception:
                        t = None
                seg.points.append(gpxpy.gpx.GPXTrackPoint(
                    latitude=float(p['lat']), longitude=float(p['lon']),
                    elevation=float(p.get('altitude', 0) or 0), time=t))
            d = os.path.dirname(out_path)
            if d:
                os.makedirs(d, exist_ok=True)
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(gpx.to_xml())
            return out_path

    # ----------------------- Экран: меню -----------------------
    class MainMenuScreen(Screen):
        def __init__(self, db, **kw):
            super().__init__(**kw)
            self.db = db
            root = BoxLayout(orientation='vertical', padding=20, spacing=15)
            root.add_widget(_auto_label(
                '[b]Трекер маршрутов[/b]\n[size=14sp]сборка %d[/size]' % BUILD,
                markup=True, font_size='30sp', color=(0.95, 0.97, 1, 1)))
            root.add_widget(Label(size_hint_y=0.08))
            palette = [(0.16, 0.55, 0.32, 1), (0.18, 0.40, 0.72, 1), (0.40, 0.30, 0.62, 1)]
            for (title, sn), bg in zip((('Начать трек', 'tracking'),
                                        ('История', 'history'),
                                        ('Статистика', 'pstats')), palette):
                b = _btn(title, bg, height=150, font_size='26sp')
                b.size_hint_y = 1
                b.bind(on_release=lambda *a, s=sn: self._go(s))
                root.add_widget(b)
            self.add_widget(root)

        def _go(self, name):
            if self.manager:
                self.manager.current = name

    # ----------------------- Экран: трекинг -----------------------
    class TrackingScreen(Screen):
        def __init__(self, db, **kw):
            super().__init__(**kw)
            self.db = db
            self.points = []
            self._pend = None
            self.tracking = False
            self.start_time = None
            self.gps = GPSService()
            self.marker = None
            self._timer = None
            self.use_service = False
            self._live = None
            root = BoxLayout(orientation='vertical', spacing=4)
            self.map = make_map(14)
            if self.map is not None:
                self.map.size_hint_y = 0.42
                root.add_widget(self.map)
            else:
                root.add_widget(Label(text='Карта недоступна (работаем без неё)',
                                      size_hint_y=0.42))
            self.trail_layer = None
            if self.map is not None and MAPVIEW_OK:
                try:
                    self.trail_layer = RouteLineLayer()
                    self.map.add_layer(self.trail_layer)
                    self.trail_layer.attach(self.map)
                except Exception as e:
                    Logger.error('trail line layer error: %s' % e)
                    self.trail_layer = None
            panel = BoxLayout(orientation='vertical', size_hint_y=0.58, spacing=5, padding=5)
            scroll = ScrollView(size_hint_y=1, do_scroll_y=True, bar_width=4,
                                bar_color=(0.3, 0.6, 1, 0.6))
            inner = BoxLayout(orientation='vertical', size_hint_y=None, spacing=4)
            inner.bind(minimum_height=inner.setter('height'))
            self.status = _auto_label('Готов к работе', color=(1, 0.86, 0.45, 1))
            self.stats = _auto_label('', color=(0.92, 0.95, 1, 1))
            inner.add_widget(self.status)
            inner.add_widget(self.stats)
            scroll.add_widget(inner)
            panel.add_widget(scroll)
            self.name_in = TextInput(
                text=datetime.now().strftime('Маршрут %Y-%m-%d %H:%M'),
                multiline=False, size_hint_y=None, height=120, font_size='13sp',
                padding=[14, 22, 14, 22])
            panel.add_widget(self.name_in)
            btns = BoxLayout(size_hint_y=None, height=104, spacing=6)
            self.b_start = _btn('Старт', (0.20, 0.70, 0.32, 1))
            self.b_stop = _btn('Стоп', (0.80, 0.25, 0.25, 1))
            self.b_save = _btn('Сохранить', (0.20, 0.45, 0.85, 1))
            self.b_menu = _btn('Меню', (0.35, 0.37, 0.45, 1))
            self.b_stop.disabled = True
            self.b_save.disabled = True
            self.b_stop.size_hint_x = 0.8
            self.b_save.size_hint_x = 1.5
            self.b_start.bind(on_press=self.start)
            self.b_stop.bind(on_press=self.stop)
            self.b_save.bind(on_press=self.save)
            self.b_menu.bind(on_press=lambda *a: self._menu())
            for b in (self.b_start, self.b_stop, self.b_save, self.b_menu):
                btns.add_widget(b)
            panel.add_widget(btns)
            root.add_widget(panel)
            self.add_widget(root)
            self._refresh()

        def _menu(self):
            if self.manager:
                self.manager.current = 'main'

        def on_pre_enter(self, *a):
            if not self.name_in.text.strip():
                self.name_in.text = datetime.now().strftime('Маршрут %Y-%m-%d %H:%M')

        def _live_path(self):
            if self._live is None:
                d = '.'
                if platform == 'android':
                    try:
                        from jnius import autoclass
                        ctx = autoclass('org.kivy.android.PythonActivity').mActivity
                        d = ctx.getExternalFilesDir(None).getAbsolutePath()
                    except Exception:
                        d = '.'
                self._live = os.path.join(d, 'track_live.json')
            return self._live

        def _read_live(self):
            try:
                with open(self._live_path()) as f:
                    return json.load(f)
            except Exception:
                return None

        def start(self, *a):
            if self.tracking:
                return
            self.points = []
            self._pend = None
            if self.marker is not None:
                map_remove_marker(self.map, self.marker)
            self.marker = None
            if self.trail_layer is not None:
                try:
                    self.trail_layer.set_points([])
                    self.trail_layer.set_current(None, None)
                except Exception:
                    pass
            map_trigger_update(self.map)
            request_ignore_battery_optimizations()
            self.tracking = True
            self.start_time = time.time()
            self.use_service = False
            if platform == 'android':
                try:
                    from jnius import autoclass
                    act = autoclass('org.kivy.android.PythonActivity').mActivity
                    svc = autoclass('org.example.routetracker.ServiceTracker')
                    svc.start(act, '')
                    self.use_service = True
                except Exception as e:
                    Logger.error('service start error: %s' % e)
            self.status.text = 'Проверка разрешения и запуск GPS...'
            try:
                self.gps.configure(self._on_loc, self._on_st)
                started = self.gps.start(1000, 0)
                msg = 'Запись. Активны провайдеры: %s\n%s' % (
                    ', '.join(started), self.gps.check_status())
                if self.use_service:
                    msg += '\nЭкран можно выключить — запись продолжится.'
                self.status.text = msg
            except Exception as e:
                self.tracking = False
                self.start_time = None
                self.status.text = 'GPS не запущен: %s\n%s' % (e, self.gps.check_status())
                self.b_start.disabled = False
                self.b_stop.disabled = True
                self.b_save.disabled = True
                return
            self.b_start.disabled = True
            self.b_stop.disabled = False
            self.b_save.disabled = True
            self._timer = Clock.schedule_interval(self._refresh, 1)

        def stop(self, *a):
            if not self.tracking:
                return
            try:
                self.gps.stop()
            except Exception:
                pass
            if self.use_service:
                try:
                    data = self._read_live()
                    if data and data.get('points'):
                        last_t = self.points[-1]['time'] if self.points else 0.0
                        extra = [p for p in data['points']
                                 if (p.get('time') or 0) > last_t + 1.0]
                        extra.sort(key=lambda p: p.get('time') or 0)
                        if extra:
                            self.points.extend(extra)
                except Exception as e:
                    Logger.error('merge service points error: %s' % e)
                try:
                    from jnius import autoclass
                    act = autoclass('org.kivy.android.PythonActivity').mActivity
                    svc = autoclass('org.example.routetracker.ServiceTracker')
                    svc.stop(act)
                except Exception as e:
                    Logger.error('service stop error: %s' % e)
                self.use_service = False
            self.tracking = False
            if self._timer:
                Clock.unschedule(self._timer)
                self._timer = None
            if self.trail_layer is not None:
                try:
                    self.trail_layer.set_points(
                        [(p['lat'], p['lon']) for p in self.points])
                except Exception:
                    pass
            self.b_start.disabled = False
            self.b_stop.disabled = True
            self.b_save.disabled = len(self.points) < 2
            if len(self.points) < 2:
                self.status.text = ('Остановлено. Точек: %d — слишком мало.\n%s'
                                    % (len(self.points), self.gps.check_status()))
            else:
                self.status.text = 'Остановлено. Точек: %d — можно сохранить.' % len(self.points)
            self._refresh()

        def _consider(self, fix):
            acc = fix.get('accuracy', 0) or 0
            if acc > 25.0:
                return
            if not self.points:
                if self._pend is None:
                    self._pend = fix
                    return
                d = _haversine_m(self._pend['lat'], self._pend['lon'],
                                 fix['lat'], fix['lon'])
                if d <= 10.0:
                    self.points.append(self._pend)
                self._pend = fix
                return
            if self._pend is None:
                self._pend = fix
                return
            d_move = _haversine_m(self.points[-1]['lat'], self.points[-1]['lon'],
                                  self._pend['lat'], self._pend['lon'])
            d_conf = _haversine_m(self._pend['lat'], self._pend['lon'],
                                  fix['lat'], fix['lon'])
            if d_move >= 5.0 and d_conf <= 12.0:
                self.points.append(self._pend)
                self._pend = fix
            elif d_conf > 12.0:
                self._pend = fix

        def _on_loc(self, fix):
            if not self.tracking:
                return
            self._consider(fix)
            if self.map is not None:
                try:
                    self.map.center_on(fix['lat'], fix['lon'])
                except Exception as e:
                    Logger.error('map update error: %s' % e)
                if self.trail_layer is not None:
                    try:
                        disp = [(p['lat'], p['lon']) for p in self.points]
                        if self._pend is not None:
                            disp.append((self._pend['lat'], self._pend['lon']))
                        self.trail_layer.set_points(disp)
                        spd = (fix.get('speed', 0) or 0) * 3.6
                        self.trail_layer.set_current(
                            fix['lat'], fix['lon'],
                            fix.get('bearing') if spd > 1.5 else None)
                    except Exception as e:
                        Logger.error('trail update error: %s' % e)
                map_trigger_update(self.map)
            acc = fix.get('accuracy', 0) or 0
            spd = (fix.get('speed', 0) or 0) * 3.6
            self.status.text = 'Точек: %d | точность: %.0f м | скорость GPS: %.1f км/ч' % (
                len(self.points), acc, spd)

        def _on_st(self, kind, provider):
            if kind in ('enabled', 'disabled'):
                self.status.text = 'Провайдер %s: %s' % (provider, kind)
            else:
                self.status.text = provider

        def _refresh(self, *a):
            if self.points:
                st = RouteCalculator.stats(self.points)
                dur = st['duration']
                if self.tracking and dur <= 0 and self.start_time:
                    dur = time.time() - self.start_time
            else:
                st = {'distance': 0.0, 'avg_speed': 0.0, 'max_speed': 0.0, 'total_ascent': 0.0}
                dur = time.time() - self.start_time if self.start_time else 0.0
            self.stats.text = (
                'Дистанция: %s | Время: %s\nСредняя: %s | Макс: %s\n'
                'Набор высоты: %.0f м | Точек: %d' % (
                    fmt_distance(st['distance']), fmt_duration(dur),
                    fmt_speed(st['avg_speed']), fmt_speed(st['max_speed']),
                    st['total_ascent'], len(self.points)))

        def save(self, *a):
            if len(self.points) < 2:
                self.status.text = 'Нет данных для сохранения (нужно >= 2 точки GPS).'
                return
            name = self.name_in.text.strip() or datetime.now().strftime('Маршрут %Y-%m-%d %H:%M')
            st = RouteCalculator.stats(self.points)
            try:
                self.db.save_route(name, st['duration'], st['distance'], st['avg_speed'],
                                   st['max_speed'], st['total_ascent'], st['total_descent'],
                                   st['min_altitude'], st['max_altitude'], self.points)
            except Exception as e:
                self.status.text = 'Ошибка БД: %s' % e
                return
            try:
                out_dir = os.path.join(App.get_running_app().user_data_dir, 'gpx')
                out_path = os.path.join(out_dir, safe_filename(name) + '.gpx')
                GPXExporter.export(self.points, name, out_path)
                self.status.text = 'Сохранено в Историю. GPX: %s' % out_path
            except Exception as e:
                self.status.text = 'Сохранено в БД, ошибка GPX: %s' % e
            self.b_save.disabled = True

    # ----------------------- Экран: история -----------------------
    class HistoryScreen(Screen):
        def __init__(self, db, **kw):
            super().__init__(**kw)
            self.db = db
            root = BoxLayout(orientation='vertical', padding=8, spacing=8)
            sv = ScrollView()
            self.grid = GridLayout(cols=1, spacing=6, size_hint_y=None)
            self.grid.bind(minimum_height=self.grid.setter('height'))
            sv.add_widget(self.grid)
            root.add_widget(sv, 1)
            back = _btn('Назад', (0.35, 0.37, 0.45, 1), height=140)
            back.bind(on_press=lambda *a: self._back())
            root.add_widget(back)
            self.add_widget(root)

        def _back(self):
            if self.manager:
                self.manager.current = 'main'

        def on_enter(self, *a):
            self.grid.clear_widgets()
            rows = self.db.get_all_routes() if self.db else []
            if not rows:
                self.grid.add_widget(_auto_label(
                    'Нет сохранённых маршрутов.\n\n'
                    'Чтобы маршрут появился: выдайте приложению разрешение '
                    '«Местоположение» (точное), включите геолокацию, '
                    '«Начать трек» → «Старт», дождитесь роста счётчика точек '
                    'у окна/на улице, затем «Стоп» → «Сохранить».'))
                return
            for rid, name, date, distance, duration, avg in rows:
                t = '%s\n%s | %s | %s | ср. %s' % (
                    name, str(date)[:19], fmt_distance(distance),
                    fmt_duration(duration), fmt_speed(avg))
                b = Button(text=t, size_hint_y=None, height=200, font_size='13sp',
                           halign='center', valign='middle')
                b.bind(on_release=lambda *a, r=rid: self._open(r))
                b.bind(size=lambda inst, v: setattr(inst, 'text_size', (v[0] - 24, None)))
                self.grid.add_widget(b)

        def _open(self, rid):
            if not self.manager:
                return
            self.manager.get_screen('stats').set_route(rid)
            self.manager.current = 'stats'

    # ----------------------- Экран: просмотр маршрута -----------------------
    class StatsScreen(Screen):
        def __init__(self, db, **kw):
            super().__init__(**kw)
            self.db = db
            self.route = None
            self.line_layer = None
            self.start_marker = None
            self.end_marker = None
            root = BoxLayout(orientation='vertical', spacing=4)
            self.map = make_map(13)
            if self.map is not None:
                self.map.size_hint_y = 0.42
                root.add_widget(self.map)
            else:
                root.add_widget(Label(text='Карта недоступна (работаем без неё)',
                                      size_hint_y=0.42))
            if self.map is not None and MAPVIEW_OK:
                try:
                    self.line_layer = RouteLineLayer()
                    self.map.add_layer(self.line_layer)
                    self.line_layer.attach(self.map)
                except Exception as e:
                    Logger.error('route line layer error: %s' % e)
                    self.line_layer = None
            panel = BoxLayout(orientation='vertical', size_hint_y=0.58, spacing=5, padding=5)
            scroll = ScrollView(size_hint_y=1, do_scroll_y=True, bar_width=4,
                                bar_color=(0.3, 0.6, 1, 0.6))
            inner = BoxLayout(orientation='vertical', size_hint_y=None, spacing=4)
            inner.bind(minimum_height=inner.setter('height'))
            self.info = _auto_label('Маршрут не выбран', markup=True, color=(0.92, 0.95, 1, 1))
            self.status = _auto_label('', color=(1, 0.86, 0.45, 1))
            inner.add_widget(self.info)
            inner.add_widget(self.status)
            scroll.add_widget(inner)
            panel.add_widget(scroll)
            btns = BoxLayout(size_hint_y=None, height=104, spacing=6)
            self.b_gpx = _btn('Экспорт GPX', (0.20, 0.45, 0.85, 1))
            self.b_del = _btn('Удалить', (0.80, 0.25, 0.25, 1))
            self.b_back = _btn('История', (0.35, 0.37, 0.45, 1))
            self.b_gpx.bind(on_press=self._gpx)
            self.b_del.bind(on_press=self._del)
            self.b_back.bind(on_press=lambda *a: self._back())
            for b in (self.b_gpx, self.b_del, self.b_back):
                btns.add_widget(b)
            panel.add_widget(btns)
            root.add_widget(panel)
            self.add_widget(root)

        def _back(self):
            if self.manager:
                self.manager.current = 'history'

        def set_route(self, rid):
            self.route = self.db.get_route_by_id(rid) if self.db else None
            self._view()

        def on_enter(self, *a):
            self._view()

        def _clear_endpoint_markers(self):
            for m in (self.start_marker, self.end_marker):
                if m is not None:
                    map_remove_marker(self.map, m)
            self.start_marker = None
            self.end_marker = None

        def _show_endpoints(self, pts):
            if self.map is None or not MAPVIEW_OK or not pts:
                return
            self._clear_endpoint_markers()
            try:
                self.start_marker = MapMarker(lat=pts[0]['lat'], lon=pts[0]['lon'])
                map_add_marker(self.map, self.start_marker)
                if len(pts) > 1:
                    self.end_marker = MapMarker(lat=pts[-1]['lat'], lon=pts[-1]['lon'])
                    map_add_marker(self.map, self.end_marker)
            except Exception as e:
                Logger.error('endpoint markers error: %s' % e)

        def _hide_endpoints(self):
            self._clear_endpoint_markers()

        def _clear_line(self):
            if self.line_layer is not None:
                try:
                    self.line_layer.set_points([])
                except Exception:
                    pass
            map_trigger_update(self.map)

        def _view(self):
            if not self.route:
                self.info.text = 'Маршрут не выбран'
                self._hide_endpoints()
                self._clear_line()
                map_trigger_update(self.map)
                return
            r = self.route
            self.info.text = (
                '[b]%s[/b]\nДата: %s\nДистанция: %s | Время: %s\n'
                'Средняя: %s | Макс: %s\nНабор: %.0f м | Спуск: %.0f м\n'
                'Мин/Макс высота: %.0f / %.0f м | Точек: %d' % (
                    r['name'], str(r['date'])[:19], fmt_distance(r['distance']),
                    fmt_duration(r['duration']), fmt_speed(r['avg_speed']),
                    fmt_speed(r['max_speed']), r['total_ascent'], r['total_descent'],
                    r['min_altitude'], r['max_altitude'], len(r.get('points', []))))
            pts = r.get('points', [])
            if not pts:
                self._hide_endpoints()
                self._clear_line()
                map_trigger_update(self.map)
                return
            if self.line_layer is not None:
                try:
                    self.line_layer.set_points([(p['lat'], p['lon']) for p in pts])
                except Exception as e:
                    Logger.error('stats line error: %s' % e)
            self._show_endpoints(pts)
            if self.map is not None:
                try:
                    self.map.center_on(pts[0]['lat'], pts[0]['lon'])
                except Exception:
                    pass
            map_trigger_update(self.map)

        def _ensure_gpx(self):
            if not self.route:
                raise ValueError('Маршрут не выбран')
            out_dir = os.path.join(App.get_running_app().user_data_dir, 'gpx')
            fn = '%s_%s.gpx' % (safe_filename(self.route['name']), self.route['id'])
            out_path = os.path.join(out_dir, fn)
            GPXExporter.export(self.route['points'], self.route['name'], out_path)
            return out_path

        def _gpx(self, *a):
            if not self.route:
                self.status.text = 'Нет маршрута'
                return
            try:
                self.status.text = 'GPX создан: %s' % self._ensure_gpx()
            except Exception as e:
                self.status.text = 'Ошибка GPX: %s' % e

        def _del(self, *a):
            if not self.route or not self.db:
                return
            try:
                self.db.delete_route(self.route['id'])
            except Exception as e:
                self.status.text = 'Ошибка удаления: %s' % e
                return
            self._hide_endpoints()
            self._clear_line()
            self.route = None
            self.info.text = 'Маршрут удалён'
            self.status.text = ''
            if self.manager:
                self.manager.current = 'history'

    # ----------------------- Экран: статистика за период -----------------------
    class PeriodStatsScreen(Screen):
        def __init__(self, db, **kw):
            super().__init__(**kw)
            self.db = db
            self.kind = 'month'
            root = BoxLayout(orientation='vertical', spacing=6, padding=8)
            root.add_widget(_auto_label('[b]Статистика за период[/b]', markup=True,
                                        font_size='22sp', color=(0.95, 0.97, 1, 1)))
            btns = BoxLayout(size_hint_y=None, height=88, spacing=6)
            for key, title in (('day', 'День'), ('week', 'Неделя'), ('month', 'Месяц'),
                               ('year', 'Год'), ('custom', 'Период')):
                b = _btn(title, (0.18, 0.40, 0.72, 1), height=88, font_size='14sp')
                b.bind(on_release=lambda *a, k=key: self._select(k))
                btns.add_widget(b)
            root.add_widget(btns)
            dates = BoxLayout(size_hint_y=None, height=88, spacing=6)
            self.d_from = TextInput(hint_text='Начало: 01.06.2026', multiline=False,
                                    font_size='13sp', padding=[10, 16, 10, 16])
            self.d_to = TextInput(hint_text='Конец: 07.08.2026', multiline=False,
                                  font_size='13sp', padding=[10, 16, 10, 16])
            dates.add_widget(self.d_from)
            dates.add_widget(self.d_to)
            root.add_widget(dates)
            scroll = ScrollView(do_scroll_y=True, bar_width=4, bar_color=(0.3, 0.6, 1, 0.6))
            inner = BoxLayout(orientation='vertical', size_hint_y=None, spacing=4)
            inner.bind(minimum_height=inner.setter('height'))
            self.report = _auto_label('', markup=True, color=(0.92, 0.95, 1, 1))
            self.cities_lbl = _auto_label('', color=(1, 0.86, 0.45, 1))
            inner.add_widget(self.report)
            inner.add_widget(self.cities_lbl)
            scroll.add_widget(inner)
            root.add_widget(scroll)
            back = _btn('Меню', (0.35, 0.37, 0.45, 1), height=100)
            back.bind(on_press=lambda *a: self._back())
            root.add_widget(back)
            self.add_widget(root)

        def _back(self):
            if self.manager:
                self.manager.current = 'main'

        def on_enter(self, *a):
            self._refresh()

        def _select(self, kind):
            self.kind = kind
            self._refresh()

        @staticmethod
        def _parse_date(s, end=False):
            s = (s or '').strip().replace('.', '-')
            try:
                d = datetime.strptime(s, '%d-%m-%Y')
            except Exception:
                try:
                    d = datetime.fromisoformat(s)
                except Exception:
                    return None
            if end:
                d = d.replace(hour=23, minute=59, second=59)
            return d

        def _bounds(self):
            now = datetime.now()
            if self.kind == 'custom':
                a = self._parse_date(self.d_from.text)
                b = self._parse_date(self.d_to.text, end=True)
                if a is None:
                    a = now.replace(hour=0, minute=0, second=0, microsecond=0)
                if b is None:
                    b = now
                return a, b
            zero = dict(hour=0, minute=0, second=0, microsecond=0)
            if self.kind == 'day':
                start = now.replace(**zero)
            elif self.kind == 'week':
                start = (now - timedelta(days=now.weekday())).replace(**zero)
            elif self.kind == 'year':
                start = now.replace(month=1, day=1, **zero)
            else:
                start = now.replace(day=1, **zero)
            return start, now

        def _routes_in(self, a, b):
            out = []
            rows = self.db.get_all_routes() if self.db else []
            for rid, _n, _d, _x, _y, _z in rows:
                r = self.db.get_route_by_id(rid) if self.db else None
                if not r:
                    continue
                try:
                    d = datetime.fromisoformat(str(r['date']))
                except Exception:
                    continue
                if a <= d <= b:
                    out.append(r)
            return out

        def _refresh(self, *a):
            a, b = self._bounds()
            routes = self._routes_in(a, b)
            if not routes:
                self.report.text = ('[b]Период:[/b] %s — %s\n'
                                    'Нет сохранённых маршрутов за выбранный период.' % (
                                        a.strftime('%d.%m.%Y'), b.strftime('%d.%m.%Y')))
                self.cities_lbl.text = ''
                return
            dist = sum(r['distance'] or 0 for r in routes)
            dur = sum(r['duration'] or 0 for r in routes)
            asc = sum(r['total_ascent'] or 0 for r in routes)
            desc = sum(r['total_descent'] or 0 for r in routes)
            mxs = max(r['max_speed'] or 0 for r in routes)
            mn_alt = min(r['min_altitude'] or 0 for r in routes)
            mx_alt = max(r['max_altitude'] or 0 for r in routes)
            longest = max(routes, key=lambda r: r['distance'] or 0)
            avg = dist / dur if dur > 0 else 0.0
            pace = (dur / 60.0) / (dist / 1000.0) if dist > 0 else 0.0
            lines = [
                '[b]Период:[/b] %s — %s' % (a.strftime('%d.%m.%Y'), b.strftime('%d.%m.%Y')),
                '[b]Маршрутов:[/b] %d' % len(routes),
                '[b]Общая дистанция:[/b] %s' % fmt_distance(dist),
                '[b]Общее время:[/b] %s' % fmt_duration(dur),
                '[b]Набор высоты:[/b] %.0f м | [b]Спуск:[/b] %.0f м' % (asc, desc),
                '[b]Средняя скорость:[/b] %s | [b]Максимальная:[/b] %s' % (
                    fmt_speed(avg), fmt_speed(mxs)),
                '[b]Мин. высота:[/b] %.0f м | [b]Макс. высота:[/b] %.0f м' % (mn_alt, mx_alt),
            ]
            if pace > 0:
                lines.append('[b]Темп:[/b] %.1f мин/км' % pace)
            else:
                lines.append('[b]Темп:[/b] —')
            lines.append('[b]Самый длинный маршрут:[/b] %s (%s)' % (
                longest['name'], fmt_distance(longest['distance'] or 0)))
            lines.append('')
            lines.append('[b]По дням:[/b]')
            by_day = {}
            for r in routes:
                key = str(r['date'])[:10]
                by_day[key] = by_day.get(key, 0.0) + (r['distance'] or 0)
            for key in sorted(by_day, reverse=True)[:14]:
                lines.append('  %s — %s' % (key, fmt_distance(by_day[key])))
            self.report.text = '\n'.join(lines)
            self.cities_lbl.text = 'Населённые пункты: вычисление…'
            self._compute_cities(routes)

        _city_cache = {}

        def _city_for(self, lat, lon):
            key = (round(float(lat), 2), round(float(lon), 2))
            if key in self._city_cache:
                return self._city_cache[key]
            city = ''
            try:
                import requests
                resp = requests.get(
                    'https://nominatim.openstreetmap.org/reverse',
                    params={'lat': lat, 'lon': lon, 'format': 'json', 'zoom': 10},
                    headers={'User-Agent': 'RouteTrackerCoursework/1.0'},
                    timeout=8)
                addr = (resp.json() or {}).get('address', {})
                city = (addr.get('city') or addr.get('town') or addr.get('village')
                        or addr.get('municipality') or '')
            except Exception:
                city = ''
            self._city_cache[key] = city
            return city

        def _compute_cities(self, routes):
            def work():
                cities = set()
                for r in routes[:10]:
                    pts = r.get('points') or []
                    if not pts:
                        continue
                    cities.add(self._city_for(pts[0]['lat'], pts[0]['lon']))
                    time.sleep(1.1)
                cities.discard('')
                Clock.schedule_once(lambda dt: self._on_cities(sorted(cities)), 0)
            threading.Thread(target=work, daemon=True).start()

        def _on_cities(self, names):
            if names:
                self.cities_lbl.text = 'Населённые пункты: %d (%s)' % (
                    len(names), ', '.join(names))
            else:
                self.cities_lbl.text = 'Населённые пункты: — (нет сети или нет данных)'

    # ----------------------- Приложение -----------------------
    class RouteTrackerApp(App):
        def build(self):
            try:
                self.db = Database(os.path.join(self.user_data_dir, 'routes.db'))
            except Exception as e:
                Logger.error('DB init error: %s' % e)
                self.db = None
            sm = ScreenManager()
            sm.add_widget(MainMenuScreen(self.db, name='main'))
            sm.add_widget(TrackingScreen(self.db, name='tracking'))
            sm.add_widget(HistoryScreen(self.db, name='history'))
            sm.add_widget(StatsScreen(self.db, name='stats'))
            sm.add_widget(PeriodStatsScreen(self.db, name='pstats'))
            return sm

        def on_start(self):
            if platform == 'android':
                Clock.schedule_once(lambda dt: request_android_permissions(), 1.0)

        def on_pause(self):
            return True

        def on_stop(self):
            try:
                t = self.root.get_screen('tracking')
                if getattr(t, 'tracking', False):
                    t.stop()
            except Exception:
                pass
            if getattr(self, 'db', None):
                try:
                    self.db.close()
                except Exception:
                    pass

    RouteTrackerApp().run()

except BaseException:
    err = _tb_text()
    _save_crash(err)
    _run_error_app('Ошибка запуска приложения', err)
