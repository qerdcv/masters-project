#!/usr/bin/env bash

LOG_FILE="/var/log/worker.log"
PID_FILE="/var/run/worker.pid"

write_log() {
  echo "[$(date "+%Y-%m-%d %H:%M:%S")] $1" >> "$LOG_FILE"
}

start_service() {
  if [ -f "$PID_FILE" ]; then
    if [ -s "$PID_FILE" ]; then
      # PID_FILE exists and is not empty, read the PID.
      read -r pid < "$PID_FILE"
      if [ -n "$pid" ] && [ -e /proc/$pid ]; then
        echo "Service is already running with PID $pid."
        exit 1
      else
        echo "PID file exists but process is not running. Cleaning up PID file."
        rm "$PID_FILE"
      fi
    else
      echo "PID file is empty, cleaning up and starting new."
      rm "$PID_FILE"
    fi
  fi

  echo "Starting service..."
  echo "Log file: $LOG_FILE"

  touch "${LOG_FILE}"

  # Start a new process group
  set -m
  (
    # Loop to keep the monitoring loop running
    while true; do
      USER_EMAIL=$(cat /etc/.lmscred)

      if [ -z "${USER_EMAIL}" ]; then
        write_log "Unable to read user email. Retrying in 3 seconds..."
        sleep 3
      else
        export USER_EMAIL
        /opt/lms/worker &

        WORKER_PID=$!
        wait $WORKER_PID
        EXIT_STATUS=$?

        if [ $EXIT_STATUS -ne 0 ]; then
          write_log "Worker task exited status $EXIT_STATUS. Retrying in 3 seconds..."
          sleep 3
        else
          write_log "Worker task stopped gracefully."
          break
        fi
      fi
    done
  ) >> "$LOG_FILE" 2>&1 &

  echo $! > "$PID_FILE"
  # Reassociate job with current session so it doesn't get terminated when the script exits
  disown -h %+
}

stop_service() {
  if [ -f "$PID_FILE" ]; then
    if [ -s "$PID_FILE" ]; then
      read -r pid < "$PID_FILE"
      if kill -0 "$pid" > /dev/null 2>&1; then
        # Use kill to send a signal to the process group
        kill -- -"$pid"
        echo "Service stopped."
      else
        echo "Process with PID $pid not found. Cleaning up PID file."
      fi
      rm -f "$PID_FILE"
    else
      echo "PID file is empty, removing."
      rm -f "$PID_FILE"
    fi
  else
    echo "Service is not running."
  fi
}

case "$1" in
  start)
  start_service
    ;;
  stop)
    stop_service
    ;;
  restart)
    stop_service
    start_service
    ;;
  *)
    echo "Usage: $0 start|stop|restart"
    exit 1
    ;;
esac

exit 0 
