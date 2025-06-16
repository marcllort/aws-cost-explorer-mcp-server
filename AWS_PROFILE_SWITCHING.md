# AWS Profile Switching Guide

The AWS Cost Explorer MCP server now supports dynamic AWS profile switching, allowing you to switch between different AWS profiles with varying permission levels during your Claude Desktop session.

## 🎯 Use Cases

### Primary Use Case: EC2 & ECS Insights
- **Problem**: EC2 and ECS performance insights require broader AWS permissions (EC2:DescribeInstances, CloudWatch:GetMetricStatistics, etc.)
- **Solution**: Switch to a profile with admin or broader permissions when you need detailed performance analysis

### Other Use Cases
- **Cross-account analysis**: Switch between profiles for different AWS accounts
- **Role-based access**: Use different profiles for different permission levels
- **Testing**: Switch between dev/staging/prod profiles

## 🔧 Available Tools

### Profile Management
- `aws_profile_list()` - List all available AWS profiles
- `aws_profile_switch(profile_name)` - Switch to a specific profile
- `aws_profile_info([profile_name])` - Get detailed info about a profile
- `aws_profile_reset()` - Reset to default credentials
- `aws_test_permissions()` - Test current profile's AWS permissions

### Enhanced Status Checking
- `get_provider_status()` - Now shows current AWS profile and account info
- `ping_server()` - Quick connectivity test with current profile

## 📋 Quick Start

### 1. List Available Profiles
```
aws_profile_list()
```
This shows all AWS profiles configured on your system with basic account info.

### 2. Switch to Admin Profile
```
aws_profile_switch('admin-profile')
```
Replace `'admin-profile'` with your actual profile name that has broader permissions.

### 3. Test Permissions
```
aws_test_permissions()
```
This will test your current profile's access to various AWS services:
- ✅ = Full access available
- ❌ = Permission denied (need different profile)
- ⚠️ = Partial access or other issues

### 4. Run EC2 Insights (with broader permissions)
```
aws_performance_ec2_insights(days=7)
```
This will now work if your current profile has EC2 and CloudWatch permissions.

## 🛡️ Permission Requirements

### Cost Explorer (Basic)
- `ce:GetCostAndUsage`
- `ce:GetDimensionValues`
- `sts:GetCallerIdentity`

### EC2 Performance Insights (Enhanced)
- All Cost Explorer permissions +
- `ec2:DescribeInstances`
- `cloudwatch:GetMetricStatistics`
- `cloudwatch:ListMetrics`

### ECS Performance Insights (Enhanced)
- All Cost Explorer permissions +
- `ecs:ListClusters`
- `ecs:DescribeServices`
- `ecs:ListServices`
- `cloudwatch:GetMetricStatistics`

## 🔄 Typical Workflow

1. **Start with Cost Analysis** (basic permissions):
   ```
   aws_cost_explorer_analyze_by_service()
   aws_cost_explorer_analyze_by_name_tag()
   ```

2. **Check Current Permissions**:
   ```
   aws_test_permissions()
   ```

3. **Switch to Admin Profile** (if needed for EC2/ECS insights):
   ```
   aws_profile_list()
   aws_profile_switch('admin-profile')
   ```

4. **Run Enhanced Analysis**:
   ```
   aws_performance_ec2_insights()
   get_ecs_performance_insights()
   get_cost_optimization_recommendations()
   ```

5. **Switch Back** (optional):
   ```
   aws_profile_reset()
   ```

## 💡 Best Practices

### Profile Setup
- **Cost Reader Profile**: Limited to Cost Explorer permissions for basic analysis
- **Admin Profile**: Broader permissions for EC2/ECS insights and optimization
- **Cross-Account Profiles**: For analyzing multiple AWS accounts

### Security
- Only switch to admin profiles when needed
- Switch back to limited profiles after analysis
- Use least-privilege principle for each profile

### Performance
- Profile switching clears all cached AWS clients
- First API call after switching may be slightly slower
- Subsequent calls use cached clients for better performance

## 🔍 Troubleshooting

### Profile Not Found
```
aws_profile_list()
```
Check if the profile exists and is properly configured.

### Permission Denied
```
aws_test_permissions()
```
Check which services are accessible with your current profile.

### Switch Failed
- Verify profile exists in `~/.aws/credentials` or `~/.aws/config`
- Ensure credentials are valid (not expired)
- Check AWS region configuration

### EC2 Insights Still Failing
- Confirm you switched to the right profile: `aws_profile_info()`
- Verify the profile has EC2 and CloudWatch permissions
- Check if you're in the right AWS region

## 🚀 Example Session

```bash
# Start with basic cost analysis
aws_cost_explorer_analyze_by_service(days=30)

# Check what profiles are available
aws_profile_list()

# Switch to admin profile for detailed insights
aws_profile_switch('admin-okta-profile')

# Verify permissions
aws_test_permissions()

# Now run enhanced analysis
aws_performance_ec2_insights(days=7)
get_ecs_performance_insights(days=7)

# Get comprehensive optimization recommendations
get_cost_optimization_recommendations(days=30)

# Switch back to limited profile
aws_profile_reset()
```

## 📊 Profile Status in Provider Report

The `get_provider_status()` tool now shows:
- Current AWS profile name
- Account ID and region
- Available capabilities based on current profile

This helps you track which profile you're currently using and what operations are available. 