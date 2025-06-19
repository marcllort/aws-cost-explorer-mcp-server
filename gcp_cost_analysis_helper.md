# GCP Cost Analysis Data Collection Guide

## Quick Data Collection Commands

### 1. Get Billing Account and Projects
```bash
# List billing accounts
gcloud billing accounts list

# List projects with billing info
gcloud projects list --format="table(projectId,name,createTime,lifecycleState)"

# Get current project billing info
gcloud billing projects describe PROJECT_ID
```

### 2. Export Billing Data (via Cloud Console)
1. Go to **Billing → Cost Table**
2. Select **Last 30 days**
3. Group by: **Service**, **Project**, **Location**
4. Export to **CSV** or **BigQuery**

### 3. Get Resource Utilization
```bash
# List Compute Engine instances with usage
gcloud compute instances list --format="table(name,zone,machineType,status,cpuPlatform)"

# Get instance utilization (requires Cloud Monitoring)
gcloud logging read "resource.type=gce_instance" --limit=100 --format=json

# List persistent disks
gcloud compute disks list --format="table(name,zone,sizeGb,type,status)"
```

### 4. Get Cost Optimization Recommendations
```bash
# Get Recommender suggestions
gcloud recommender recommendations list --project=PROJECT_ID --recommender=google.compute.instance.MachineTypeRecommender

# Get rightsizing recommendations
gcloud recommender recommendations list --project=PROJECT_ID --recommender=google.compute.disk.IdleResourceRecommender
```

### 5. BigQuery Cost Analysis (if billing export is set up)
```sql
-- Total costs by service (last 30 days)
SELECT 
  service.description as service_name,
  SUM(cost) as total_cost,
  currency
FROM `PROJECT.DATASET.gcp_billing_export_v1_BILLING_ACCOUNT_ID`
WHERE _PARTITIONTIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY service.description, currency
ORDER BY total_cost DESC

-- Costs by project
SELECT 
  project.id as project_id,
  project.name as project_name,
  SUM(cost) as total_cost,
  currency
FROM `PROJECT.DATASET.gcp_billing_export_v1_BILLING_ACCOUNT_ID`
WHERE _PARTITIONTIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY project.id, project.name, currency
ORDER BY total_cost DESC

-- Daily cost trends
SELECT 
  DATE(usage_start_time) as date,
  SUM(cost) as daily_cost,
  currency
FROM `PROJECT.DATASET.gcp_billing_export_v1_BILLING_ACCOUNT_ID`
WHERE _PARTITIONTIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY DATE(usage_start_time), currency
ORDER BY date DESC
```

## Report Template Structure

### Executive Summary
- **Total Cost**: $[FROM_BILLING_CONSOLE]
- **Top 3 Services**: [FROM_CSV_EXPORT]
- **Biggest Changes**: [COMPARE_MONTH_OVER_MONTH]

### Service Analysis

#### Compute Engine
- **Instance Types**: [FROM_gcloud_compute_instances_list]
- **Utilization**: [FROM_CLOUD_MONITORING]
- **Recommendations**: [FROM_RECOMMENDER]

#### Cloud Storage
- **Storage Classes**: [FROM_BILLING_BREAKDOWN]
- **Lifecycle Policies**: [CHECK_BUCKET_SETTINGS]

#### Cloud SQL
- **Instance Types**: [FROM_gcloud_sql_instances_list]
- **Storage Usage**: [FROM_BILLING_BREAKDOWN]

### Optimization Opportunities
- **Rightsizing**: [FROM_RECOMMENDER]
- **Preemptible Instances**: [MANUAL_ANALYSIS]
- **Committed Use Discounts**: [FROM_BILLING_CONSOLE]

## Key Metrics to Track

1. **Daily Cost Trend**: Export from Billing Console
2. **Service Breakdown**: Group by Service in Cost Table
3. **Project Breakdown**: Group by Project in Cost Table
4. **Instance Utilization**: Cloud Monitoring dashboards
5. **Storage Growth**: Cloud Storage analytics
6. **Recommender Savings**: Recommender API suggestions

## Manual Analysis Steps

1. **Download billing data** as CSV from GCP Console
2. **Compare month-over-month** changes in Excel/Sheets
3. **Check Cloud Monitoring** for resource utilization
4. **Review Recommender** suggestions for savings opportunities
5. **Analyze machine types** for migration opportunities (N1→E2)
6. **Check for unused resources** (disks, IPs, etc.)

This guide helps you collect the data manually while we fix the automated tools. 