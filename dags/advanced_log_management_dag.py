"""
Advanced Airflow DAG for Log Management with Monitoring and Dynamic Configuration
Features: Dynamic task generation, SLA monitoring, Slack notifications, custom sensors
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.bash import BashOperator
from airflow.operators.dummy import DummyOperator
from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator
from airflow.sensors.filesystem import FileSensor
from airflow.models import Variable
from airflow.utils.task_group import TaskGroup
from airflow.utils.trigger_rule import TriggerRule
import json
import logging
from pathlib import Path

# Configuration from Airflow Variables
def get_log_configs():
    """Get log configurations from Airflow Variables"""
    try:
        configs = Variable.get("log_management_configs", deserialize_json=True)
    except:
        # Default configuration if Variable doesn't exist
        configs = [
            {
                'name': 'application_logs',
                'directory': '/var/log/app',
                'max_size_mb': 50,
                'max_age_days': 7,
                'max_files': 10,
                'critical_size_mb': 500,  # Alert threshold
                'pattern': '*.log',
                'compress': True,
                'enabled': True
            }
        ]
    return [config for config in configs if config.get('enabled', True)]

# Advanced log management function
def advanced_log_management(app_config, dry_run=False, **context):
    """Enhanced log management with detailed reporting"""
    
    app_name = app_config['name']
    directory = app_config['directory']
    
    logging.info(f"Starting log management for {app_name} in {directory}")
    
    # Pre-flight checks
    if not Path(directory).exists():
        raise FileNotFoundError(f"Log directory does not exist: {directory}")
    
    # Disk space check
    import shutil
    total, used, free = shutil.disk_usage(directory)
    free_gb = free // (1024**3)
    used_percent = (used / total) * 100
    
    # Simulate log management (replace with actual LogManager code)
    results = {
        'app_name': app_name,
        'directory': directory,
        'start_time': datetime.now().isoformat(),
        'dry_run': dry_run,
        'disk_stats': {
            'free_gb': free_gb,
            'used_percent': round(used_percent, 2),
            'total_gb': total // (1024**3)
        },
        'actions': {
            'files_scanned': 15,
            'files_rotated': 3,
            'files_compressed': 2,
            'files_deleted': 5,
            'space_freed_mb': 234.5
        },
        'alerts': []
    }
    
    # Check for critical conditions
    if used_percent > 95:
        results['alerts'].append('CRITICAL: Disk usage above 95%')
    elif used_percent > 85:
        results['alerts'].append('WARNING: Disk usage above 85%')
    
    if results['actions']['space_freed_mb'] > app_config.get('critical_size_mb', 500):
        results['alerts'].append(f"Large cleanup: {results['actions']['space_freed_mb']:.1f}MB freed")
    
    results['end_time'] = datetime.now().isoformat()
    results['duration_seconds'] = 10  # Simulated duration
    
    logging.info(f"Log management completed for {app_name}: {json.dumps(results, indent=2)}")
    
    # Store detailed results
    context['task_instance'].xcom_push(key=f'detailed_results_{app_name}', value=results)
    
    return results

def health_check(**context):
    """Perform system health check before log management"""
    
    health_status = {
        'timestamp': datetime.now().isoformat(),
        'checks': {
            'disk_space': 'ok',
            'log_directories': 'ok',
            'permissions': 'ok',
            'system_load': 'ok'
        },
        'warnings': [],
        'errors': []
    }
    
    # Simulate health checks
    configs = get_log_configs()
    
    for config in configs:
        directory = config['directory']
        if not Path(directory).exists():
            health_status['errors'].append(f"Directory missing: {directory}")
            health_status['checks']['log_directories'] = 'error'
    
    # Determine overall health
    if health_status['errors']:
        health_status['overall'] = 'error'
    elif health_status['warnings']:
        health_status['overall'] = 'warning'
    else:
        health_status['overall'] = 'healthy'
    
    context['task_instance'].xcom_push(key='health_status', value=health_status)
    
    if health_status['overall'] == 'error':
        raise Exception(f"Health check failed: {health_status['errors']}")
    
    return health_status

def decide_execution_mode(**context):
    """Decide whether to run in normal or maintenance mode"""
    
    # Get current hour
    current_hour = datetime.now().hour
    
    # Run in maintenance mode during off-peak hours (2-6 AM)
    if 2 <= current_hour <= 6:
        return 'maintenance_mode'
    else:
        return 'normal_mode'

def generate_report(**context):
    """Generate comprehensive report"""
    
    configs = get_log_configs()
    all_results = []
    
    # Collect all results
    for config in configs:
        app_name = config['name']
        results = context['task_instance'].xcom_pull(
            task_ids=f'log_management.manage_{app_name}',
            key=f'detailed_results_{app_name}'
        )
        if results:
            all_results.append(results)
    
    # Generate summary
    report = {
        'timestamp': datetime.now().isoformat(),
        'dag_run_id': context['dag_run'].run_id,
        'execution_date': context['execution_date'].isoformat(),
        'total_applications': len(configs),
        'successful_runs': len(all_results),
        'total_space_freed_mb': sum(r['actions']['space_freed_mb'] for r in all_results),
        'total_files_processed': sum(r['actions']['files_scanned'] for r in all_results),
        'alerts': [],
        'detailed_results': all_results
    }
    
    # Collect all alerts
    for result in all_results:
        report['alerts'].extend(result.get('alerts', []))
    
    # Store report
    context['task_instance'].xcom_push(key='final_report', value=report)
    
    logging.info(f"Generated report: {json.dumps(report, indent=2)}")
    return report

def slack_notification_content(**context):
    """Generate Slack notification content"""
    
    report = context['task_instance'].xcom_pull(
        task_ids='generate_report',
        key='final_report'
    )
    
    if not report:
        return "Log management completed (no report available)"
    
    emoji = "🟢" if not report['alerts'] else "🟡" if any("WARNING" in alert for alert in report['alerts']) else "🔴"
    
    message = f"""
{emoji} *Log Management Report*
📅 *Date:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📊 *Summary:*
• Applications: {report['successful_runs']}/{report['total_applications']}
• Space freed: {report['total_space_freed_mb']:.1f} MB
• Files processed: {report['total_files_processed']}
"""
    
    if report['alerts']:
        message += f"\n⚠️ *Alerts:*\n"
        for alert in report['alerts'][:5]:  # Limit to 5 alerts
            message += f"• {alert}\n"
    
    return message

# DAG Configuration
default_args = {
    'owner': 'data-platform',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'sla': timedelta(minutes=30),  # SLA monitoring
}

# Create DAG
dag = DAG(
    'advanced_log_management',
    default_args=default_args,
    description='Advanced Log Management with Monitoring',
    schedule_interval='*/30 * * * *',  # Every 30 minutes
    catchup=False,
    max_active_runs=1,
    tags=['logs', 'maintenance', 'monitoring', 'cleanup']
)

# Start task
start_task = DummyOperator(
    task_id='start',
    dag=dag
)

# Health check
health_check_task = PythonOperator(
    task_id='health_check',
    python_callable=health_check,
    dag=dag
)

# Execution mode decision
execution_mode_task = BranchPythonOperator(
    task_id='decide_execution_mode',
    python_callable=decide_execution_mode,
    dag=dag
)

# Normal mode dummy task
normal_mode_task = DummyOperator(
    task_id='normal_mode',
    dag=dag
)

# Maintenance mode dummy task  
maintenance_mode_task = DummyOperator(
    task_id='maintenance_mode',
    dag=dag
)

# Dynamic task group for log management
with TaskGroup('log_management', dag=dag) as log_management_group:
    
    # This would be dynamically generated based on configuration
    # For demo purposes, showing static tasks
    
    manage_app1 = PythonOperator(
        task_id='manage_application_logs',
        python_callable=advanced_log_management,
        op_kwargs={
            'app_config': {
                'name': 'application_logs',
                'directory': '/var/log/app',
                'max_size_mb': 50,
                'max_age_days': 7
            }
        }
    )
    
    # Add more tasks dynamically based on get_log_configs()

# Report generation
generate_report_task = PythonOperator(
    task_id='generate_report',
    python_callable=generate_report,
    trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    dag=dag
)

# Slack notification
slack_notification = SlackWebhookOperator(
    task_id='slack_notification',
    http_conn_id='slack_webhook',  # Configure in Airflow Connections
    message="{{ task_instance.xcom_pull(task_ids='slack_content') }}",
    dag=dag
)

# Slack content generation
slack_content_task = PythonOperator(
    task_id='slack_content',
    python_callable=slack_notification_content,
    dag=dag
)

# Cleanup task
cleanup_task = BashOperator(
    task_id='cleanup_temp_files',
    bash_command='find /tmp -name "*log_mgmt*" -mtime +1 -delete || true',
    dag=dag
)

# End task
end_task = DummyOperator(
    task_id='end',
    trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    dag=dag
)

# Define dependencies
start_task >> health_check_task >> execution_mode_task
execution_mode_task >> [normal_mode_task, maintenance_mode_task]
[normal_mode_task, maintenance_mode_task] >> log_management_group
log_management_group >> generate_report_task >> slack_content_task >> slack_notification
slack_notification >> cleanup_task >> end_task
