#!/bin/bash

# Copyright © Sachin Chandrashekhar - Data Engineering Hub. All Rights Reserved.
#
# This code is provided as part of a paid training program.
# Unauthorized copying, distribution, or
# publication of this code—either in whole or in part—
# is strictly prohibited.
#
# This code may NOT be:
# - Uploaded to public repositories (GitHub, GitLab, etc.)
# - Shared with third parties
# - Used for commercial purposes
#
# Licensed for personal educational use only.
#
# If this code is found on a public repository or distributed without
# authorization, please notify: legal@dataengineeringhub.in

set -e

LOG_FILE="mission-deh-hof-ec2-teardown-$(date +%Y%m%d-%H%M%S).log"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "Starting EC2 teardown..."

# Check if details file exists
if [ ! -f "mission-deh-hof-ec2-details.txt" ]; then
    log "WARNING: mission-deh-hof-ec2-details.txt not found. Will search for resources by name/tag."
    INSTANCE_ID=""
    SG_ID=""
    KEY_NAME="mission-deh-hof-unix-key"
    ROLE_NAME="mission-deh-hof-unix-role"
    INSTANCE_PROFILE_NAME="mission-deh-hof-unix-profile"
else
    log "Loading instance details from mission-deh-hof-ec2-details.txt"
    . ./mission-deh-hof-ec2-details.txt
fi

# Find instance if not in details file
if [ -z "$INSTANCE_ID" ]; then
    log "Searching for EC2 instance with tag Name=mission-deh-hof-unix-training..."
    INSTANCE_ID=$(aws ec2 describe-instances \
        --filters "Name=tag:Name,Values=mission-deh-hof-unix-training" "Name=instance-state-name,Values=running,stopped,stopping,pending" \
        --query "Reservations[0].Instances[0].InstanceId" \
        --output text \
        --no-cli-pager 2>/dev/null || echo "")
fi

# Terminate EC2 instance
if [ -n "$INSTANCE_ID" ] && [ "$INSTANCE_ID" != "None" ]; then
    log "Terminating EC2 instance: $INSTANCE_ID"
    aws ec2 terminate-instances --instance-ids "$INSTANCE_ID" --no-cli-pager 2>&1 | tee -a "$LOG_FILE"
    
    log "Waiting for instance to terminate..."
    aws ec2 wait instance-terminated --instance-ids "$INSTANCE_ID" --no-cli-pager
    log "Instance terminated successfully"
else
    log "No instance found to terminate"
fi

# Find security group if not in details file
if [ -z "$SG_ID" ]; then
    log "Searching for security group: mission-deh-hof-unix-sg..."
    SG_ID=$(aws ec2 describe-security-groups \
        --filters "Name=group-name,Values=mission-deh-hof-unix-sg" \
        --query "SecurityGroups[0].GroupId" \
        --output text \
        --no-cli-pager 2>/dev/null || echo "")
fi

# Delete security group
if [ -n "$SG_ID" ] && [ "$SG_ID" != "None" ]; then
    log "Deleting security group: $SG_ID"
    aws ec2 delete-security-group --group-id "$SG_ID" --no-cli-pager 2>&1 | tee -a "$LOG_FILE"
    log "Security group deleted successfully"
else
    log "No security group found to delete"
fi

# Delete instance profile and role
if [ -n "$INSTANCE_PROFILE_NAME" ]; then
    log "Removing role from instance profile..."
    aws iam remove-role-from-instance-profile --instance-profile-name "$INSTANCE_PROFILE_NAME" --role-name "${ROLE_NAME:-mission-deh-hof-unix-role}" --no-cli-pager 2>&1 | tee -a "$LOG_FILE" || log "Instance profile not found"
    
    log "Deleting instance profile: $INSTANCE_PROFILE_NAME"
    aws iam delete-instance-profile --instance-profile-name "$INSTANCE_PROFILE_NAME" --no-cli-pager 2>&1 | tee -a "$LOG_FILE" || log "Instance profile not found"
fi

if [ -n "$ROLE_NAME" ]; then
    log "Detaching SSM policy from role..."
    aws iam detach-role-policy --role-name "$ROLE_NAME" --policy-arn "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore" --no-cli-pager 2>&1 | tee -a "$LOG_FILE" || log "Policy not attached"
    
    log "Deleting IAM role: $ROLE_NAME"
    aws iam delete-role --role-name "$ROLE_NAME" --no-cli-pager 2>&1 | tee -a "$LOG_FILE" || log "Role not found"
fi

# Delete key pair
if [ -n "$KEY_NAME" ]; then
    log "Deleting key pair: $KEY_NAME"
    aws ec2 delete-key-pair --key-name "$KEY_NAME" --no-cli-pager 2>&1 | tee -a "$LOG_FILE" || log "Key pair not found in AWS"
    
    if [ -f "${KEY_NAME}.pem" ]; then
        log "Removing local key file: ${KEY_NAME}.pem"
        rm -f "${KEY_NAME}.pem"
    fi
    log "Key pair cleanup completed"
else
    log "No key pair specified"
fi

# Remove details file
if [ -f "mission-deh-hof-ec2-details.txt" ]; then
    log "Removing details file: mission-deh-hof-ec2-details.txt"
    rm -f mission-deh-hof-ec2-details.txt
fi

log "=========================================="
log "EC2 Teardown Complete!"
log "=========================================="
log "All resources have been cleaned up."
log "Log file: $LOG_FILE"
log "=========================================="
