# Viewer

[![Build Status](https://travis-ci.org/openearth/vegetatiemonitor-service.svg?branch=master)](https://travis-ci.org/openearth/vegetatiemonitor-service)

> Main repository of the viewer: https://github.com/openearth/vegetatiemonitor

# vegetatiemonitor-service
Service for the communication between vegetatiemonitor viewer and GEE

From app/ directory:

Deploy app, optionally: -v <version> - a bit faster:

gcloud app deploy --project vegetatie-monitor

Browse: 

gcloud app browse

To deploy/update cron job, run:
gcloud app deploy cron.yaml

