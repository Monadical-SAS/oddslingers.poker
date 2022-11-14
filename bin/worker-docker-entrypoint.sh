#!/bin/bash
cp /etc/supervisor/oddslingers-docker-prod-worker.conf /etc/supervisor/conf.d/supervisord.conf
supervisord
