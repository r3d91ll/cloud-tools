# AWS Script Runner - Deployment Guide

This document provides instructions for deploying the AWS Script Runner backend service in various environments.

## Prerequisites

Before deploying the application, ensure you have the following:

- Python 3.10 or higher
- pip (Python package manager)
- PostgreSQL database
- AWS credentials with appropriate permissions for:
  - AWS SSM (Systems Manager)
  - EC2 instance management
  - STS (Security Token Service) for role assumption
- Network access to AWS services

## Local Development Deployment

For local development and testing:

1. Clone the repository:
   ```bash
   git clone https://github.com/TexasDIR/PCM-Ops_AWSScriptRunner.git
   cd PCM-Ops_AWSScriptRunner/new-code
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

4. Set up environment variables (create a `.env` file in the backend directory):
   ```
   # Database configuration
   DATABASE_URL=postgresql://user:password@localhost/aws_script_runner
   
   # AWS configuration
   AWS_REGION=us-west-2
   AWS_PROFILE=default  # Optional, if using AWS profiles
   
   # Application settings
   DEBUG=True
   SECRET_KEY=your_secret_key_here
   ```

5. Create the database:
   ```bash
   # Using psql
   psql -U postgres -c "CREATE DATABASE aws_script_runner;"
   
   # Initialize the database with models
   cd backend
   python -m app.db.init_db
   ```

6. Run the development server:
   ```bash
   uvicorn app.main:app --reload
   ```

7. Access the API documentation at `http://localhost:8000/docs`

## Production Deployment

For production deployment, we recommend using Docker containers.

### Docker Deployment

1. Build the Docker image:
   ```bash
   cd PCM-Ops_AWSScriptRunner/new-code
   docker build -t aws-script-runner -f backend/Dockerfile .
   ```

2. Create a Docker Compose file (`docker-compose.yml`):
   ```yaml
   version: '3'
   
   services:
     api:
       image: aws-script-runner
       ports:
         - "8000:8000"
       environment:
         - DATABASE_URL=postgresql://user:password@db:5432/aws_script_runner
         - AWS_REGION=us-west-2
         - DEBUG=False
         - SECRET_KEY=your_production_secret_key
         - ALLOWED_HOSTS=your-domain.com,localhost
       depends_on:
         - db
     
     db:
       image: postgres:14
       volumes:
         - postgres_data:/var/lib/postgresql/data/
       environment:
         - POSTGRES_USER=user
         - POSTGRES_PASSWORD=password
         - POSTGRES_DB=aws_script_runner
   
   volumes:
     postgres_data:
   ```

3. Start the services:
   ```bash
   docker-compose up -d
   ```

4. Initialize the database:
   ```bash
   docker-compose exec api python -m app.db.init_db
   ```

### Kubernetes Deployment

For larger scale deployments, Kubernetes is recommended:

1. Create Kubernetes deployment files:

   **database.yaml**:
   ```yaml
   apiVersion: v1
   kind: PersistentVolumeClaim
   metadata:
     name: postgres-pvc
   spec:
     accessModes:
       - ReadWriteOnce
     resources:
       requests:
         storage: 10Gi
   ---
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: postgres
   spec:
     replicas: 1
     selector:
       matchLabels:
         app: postgres
     template:
       metadata:
         labels:
           app: postgres
       spec:
         containers:
           - name: postgres
             image: postgres:14
             ports:
               - containerPort: 5432
             env:
               - name: POSTGRES_USER
                 valueFrom:
                   secretKeyRef:
                     name: db-credentials
                     key: username
               - name: POSTGRES_PASSWORD
                 valueFrom:
                   secretKeyRef:
                     name: db-credentials
                     key: password
               - name: POSTGRES_DB
                 value: aws_script_runner
             volumeMounts:
               - name: postgres-storage
                 mountPath: /var/lib/postgresql/data
         volumes:
           - name: postgres-storage
             persistentVolumeClaim:
               claimName: postgres-pvc
   ---
   apiVersion: v1
   kind: Service
   metadata:
     name: postgres
   spec:
     selector:
       app: postgres
     ports:
       - port: 5432
         targetPort: 5432
   ```

   **api.yaml**:
   ```yaml
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: aws-script-runner
   spec:
     replicas: 3
     selector:
       matchLabels:
         app: aws-script-runner
     template:
       metadata:
         labels:
           app: aws-script-runner
       spec:
         containers:
           - name: aws-script-runner
             image: aws-script-runner:latest
             ports:
               - containerPort: 8000
             env:
               - name: DATABASE_URL
                 value: postgresql://$(DB_USER):$(DB_PASSWORD)@postgres:5432/aws_script_runner
               - name: DB_USER
                 valueFrom:
                   secretKeyRef:
                     name: db-credentials
                     key: username
               - name: DB_PASSWORD
                 valueFrom:
                   secretKeyRef:
                     name: db-credentials
                     key: password
               - name: SECRET_KEY
                 valueFrom:
                   secretKeyRef:
                     name: api-credentials
                     key: secret-key
               - name: AWS_REGION
                 value: us-west-2
               - name: DEBUG
                 value: "False"
               - name: ALLOWED_HOSTS
                 value: "your-domain.com,localhost"
   ---
   apiVersion: v1
   kind: Service
   metadata:
     name: aws-script-runner
   spec:
     selector:
       app: aws-script-runner
     ports:
       - port: 80
         targetPort: 8000
     type: LoadBalancer
   ```

2. Create the required secrets:
   ```bash
   kubectl create secret generic db-credentials \
     --from-literal=username=dbuser \
     --from-literal=password=dbpassword
   
   kubectl create secret generic api-credentials \
     --from-literal=secret-key=your_production_secret_key
   ```

3. Apply the Kubernetes configuration:
   ```bash
   kubectl apply -f database.yaml
   kubectl apply -f api.yaml
   ```

4. Initialize the database:
   ```bash
   # Get the name of a running pod
   POD_NAME=$(kubectl get pods -l app=aws-script-runner -o jsonpath="{.items[0].metadata.name}")
   
   # Run the database initialization
   kubectl exec $POD_NAME -- python -m app.db.init_db
   ```

## Security Considerations

- Always use secure database credentials
- Store secrets in a secure vault (e.g., AWS Secrets Manager, HashiCorp Vault)
- Configure HTTPS with proper certificates
- Set up appropriate IAM roles with least privilege
- Implement network security groups/rules to restrict access
- Regularly update dependencies to address vulnerabilities

## Monitoring and Logging

We recommend:

1. Set up monitoring using:
   - AWS CloudWatch
   - Prometheus and Grafana
   - Datadog

2. Configure logging:
   - Enable application logging
   - Centralize logs using ELK stack or CloudWatch Logs
   - Set up log retention policies

## Troubleshooting

Common deployment issues and solutions:

1. **Database connection issues**:
   - Check database credentials
   - Verify network connectivity and security groups
   - Ensure database is running and accessible

2. **AWS credential problems**:
   - Verify IAM permissions
   - Check credential expiration
   - Test AWS CLI connectivity

3. **Application errors**:
   - Check application logs
   - Verify environment variables
   - Test API endpoints after deployment

## Backup and Disaster Recovery

1. **Database Backups**:
   - Configure regular database backups
   - Test database restoration process
   - Store backups in a secure location

2. **High Availability**:
   - Deploy in multiple availability zones
   - Set up database replication
   - Configure auto-scaling for the application

## Maintenance and Updates

1. **Update Process**:
   - Use rolling updates to minimize downtime
   - Test updates in a staging environment before production
   - Maintain a rollback plan

2. **Version Control**:
   - Tag releases in your repository
   - Document changes in release notes
   - Track deployed versions

## Support

For deployment issues, contact the PCM-Ops team at support@texasdir.gov.
