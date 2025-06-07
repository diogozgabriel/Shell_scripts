#!/bin/bash
# Script: schedule_hrd.sh
# Description: Schedule the execution of the H_R_D.sh script using the 'at' command.
# Usage: ./schedule_hrd.sh

# === Check if 'at' is installed ===
if ! command -v at &> /dev/null; then
    echo "'at' command is not installed. Please install it to continue."
    exit 1
fi

# === Prompt for date and time ===
read -p "Enter the date (DD-MM-YYYY): " DATE
read -p "Enter the time (HH:MM): " TIME

# === Validate date and time ===
if ! date -d "$DATE $TIME" &> /dev/null; then
    echo "Invalid date or time format."
    exit 1
fi

# === Check if the script to be scheduled exists ===
if [ ! -f ./H_R_D.sh ]; then
    echo "The script 'H_R_D.sh' was not found in the current directory."
    exit 1
fi

# === Create logs directory if it does not exist ===
mkdir -p logs

# === Generate a unique log filename with timestamp ===
LOG_FILE="logs/output_$(date +%Y%m%d_%H%M%S).log"

# === Schedule the task ===
echo "./H_R_D.sh > $LOG_FILE" | at $TIME $DATE

# === Confirmation message ===
echo "Task successfully scheduled for $DATE at $TIME."
