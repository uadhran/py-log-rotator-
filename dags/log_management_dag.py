from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.email import EmailOperator
from airflow.models import Variable
from datetime import datetime, timedelta
from src.log_rotator.core import process_logs, load_config  # Import from core
import os
import logging
import jinja2  # For HTML email templates

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 9, 4),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'advanced_log_management',
    default_args=default_args,
    description='Orchestrated log rotation and management',
    schedule_interval='*/30 * * * *',  # Every 30 minutes
    catchup=False,
    max_active_runs=1,
    tags=['logs', 'rotation'],
    sla=timedelta(minutes=30),  # SLA monitoring
)

def health_check(**context):
    """Pre-flight health check."""
    # Check disk space, permissions, etc.
    if os.path.exists('/var/log') and os.access('/var/log', os.W_OK):
        logging.info("Health check passed.")
        return 'execute_logs'
    else:
        logging.error("Health check failed.")
        return 'send_error_email'

def execution_mode_decision(**context):
    """Decide mode: report or full execution."""
    # For simplicity, always full execution; customize as needed
    return 'manage_logs'

def manage_logs(**context):
    """Process logs using core.py logic."""
    config_data = Variable.get('scattered_log_configs')
    report = process_logs(config_data=config_data, dry_run=False)
    context['ti'].xcom_push(key='report', value=report)
    return report

def aggregate_results(**context):
    """Aggregate results from parallel tasks (if any)."""
    report = context['ti'].xcom_pull(key='report')
    return report

# HTML email template (embedded for simplicity)
email_template = """
<!DOCTYPE html>
<html>
<head><style>body {font-family: Arial;} .status {color: green;}</style></head>
<body>
<h1>Log Rotation Report</h1>
<p>Status: <span class="status">Success</span></p>
<ul>
    <li>Directories Managed: {{ directories_managed }}</li>
    <li>Files Processed: {{ files_processed }}</li>
    <li>Space Freed: {{ space_freed_mb }} MB</li>
</ul>
<p>Timestamp: {{ timestamp }}</p>
</body>
</html>
"""

def render_email(report):
    template = jinja2.Template(email_template)
    return template.render(**report)

send_report_email = EmailOperator(
    task_id='send_report_email',
    to='your-email@company.com',  # Configure in airflow.cfg
    subject='Log Rotation Summary',
    html_content="{{ ti.xcom_pull(task_ids='aggregate_results') | render_email }}",  # Jinja in email
    dag=dag,
)

send_error_email = EmailOperator(
    task_id='send_error_email',
    to='your-email@company.com',
    subject='Log Rotation Error',
    html_content='<h1>Error: Health check failed!</h1>',
    dag=dag,
)

# Task definitions
health_check_task = BranchPythonOperator(
    task_id='health_check',
    python_callable=health_check,
    dag=dag,
)

mode_decision_task = BranchPythonOperator(
    task_id='execution_mode_decision',
    python_callable=execution_mode_decision,
    dag=dag,
)

manage_logs_task = PythonOperator(
    task_id='manage_logs',
    python_callable=manage_logs,
    dag=dag,
)

aggregate_task = PythonOperator(
    task_id='aggregate_results',
    python_callable=aggregate_results,
    dag=dag,
)

# Task flow
health_check_task >> mode_decision_task >> manage_logs_task >> aggregate_task >> send_report_email
health_check_task >> send_error_email
