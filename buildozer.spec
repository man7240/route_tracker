[app]
title = Трекер маршрутов
package.name = routetracker
package.domain = org.example

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf

version = 1.0

requirements = python3,kivy==2.3.1,filetype,plyer,gpxpy,requests,kivy_garden.mapview,pyjnius,android,libffi,openssl,setuptools,six,certifi

orientation = portrait
fullscreen = 0

icon.filename = ./icon.png
presplash.filename = ./presplash.png
android.presplash_color = #06070A

android.permissions = INTERNET,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,ACCESS_BACKGROUND_LOCATION,WAKE_LOCK,FOREGROUND_SERVICE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

android.api = 33
android.minapi = 21
android.archs = arm64-v8a

android.accept_sdk_license = True
android.allow_backup = True

services = tracker:service/tracker_service.py:foreground

p4a.fork = kivy
p4a.branch = release-2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
