# Nova Prompt Optimizer Frontend

A web-based interface for the Nova Prompt Optimizer SDK, providing an intuitive way to create, optimize, and manage prompts using Amazon's Nova models.

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- AWS credentials configured
- Access to Amazon Bedrock Nova models

### Installation

1. **Clone and navigate to frontend:**
   ```bash
   cd frontend
   ```

2. **Create virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure AWS credentials:**
   ```bash
   export AWS_ACCESS_KEY_ID="your-access-key"
   export AWS_SECRET_ACCESS_KEY="your-secret-key"
   export AWS_DEFAULT_REGION="us-east-1"
   ```

### Running the Application

```bash
python app.py
```

The application will start on `http://localhost:8000`

## 📊 Data Storage & Management

### Database Structure
The frontend uses SQLite (`nova_optimizer.db`) to store all application data:

#### **Datasets Table**
- **Purpose**: Stores uploaded and generated datasets
- **Data**: Dataset metadata, file paths, row counts, creation dates
- **Files**: Actual dataset files saved in `uploads/` directory
- **Formats**: JSON, CSV, JSONL supported

#### **Prompts Table**
- **Purpose**: Stores prompt templates and configurations
- **Data**: Prompt text, variables, performance metrics, usage history
- **Metadata**: Creation date, last used, optimization results

#### **Optimizations Table**
- **Purpose**: Tracks optimization jobs and results
- **Data**: Optimization status, progress, improvement metrics
- **Results**: Optimized prompts, performance comparisons, logs

#### **Metrics Table**
- **Purpose**: Stores custom evaluation metrics
- **Data**: Metric code, descriptions, scoring criteria
- **Usage**: Tracks metric usage and performance

#### **Optimization Logs Table**
- **Purpose**: Detailed logs for optimization processes
- **Data**: Timestamped log entries, error messages, debug info
- **Tracking**: Real-time optimization progress and issues

### File Storage
- **Datasets**: Saved in `uploads/` directory with unique filenames
- **Results**: Optimization results stored in `temp_results/` (temporary)
- **Database**: All metadata and relationships stored in SQLite
- **Static Assets**: UI assets in `static/` directory

### Data Flow
1. **Upload**: Files uploaded to `uploads/`, metadata saved to database
2. **Processing**: SDK processes data, logs saved to optimization_logs
3. **Results**: Optimized prompts saved to database with performance metrics
4. **Persistence**: All data persists across application restarts

## 🏗️ Architecture

### Core Components
- **`app.py`** - FastHTML web application
- **`database.py`** - SQLite database layer
- **`sdk_worker.py`** - Nova SDK integration
- **`config.py`** - Application configuration

### Directory Structure
```
frontend/
├── app.py              # Main application
├── database.py         # Database operations
├── sdk_worker.py       # SDK integration
├── config.py           # Configuration
├── prompt_templates.py # Prompt templates
├── components/         # UI components
├── routes/            # Route handlers
├── services/          # Business logic
├── static/            # Static assets
├── docs/              # Documentation
└── tests/             # Test files
```

### Key Features
- **Dataset Management**: Upload, generate, and manage training datasets
- **Prompt Building**: Visual prompt builder with templates
- **Optimization**: Automated prompt optimization using Nova models
- **Metrics**: Custom evaluation metrics for prompt performance
- **Real-time Logs**: Live optimization progress tracking

## 🔧 Configuration

### Environment Variables
- `AWS_ACCESS_KEY_ID` - AWS access key
- `AWS_SECRET_ACCESS_KEY` - AWS secret key
- `AWS_DEFAULT_REGION` - AWS region (default: us-east-1)
- `NOVA_RATE_LIMIT` - API rate limit (default: 2 TPS)

### Model Configuration
The application supports all Nova models:
- **nova-micro-v1:0** - Fastest, lowest cost
- **nova-lite-v1:0** - Balanced performance
- **nova-pro-v1:0** - High performance
- **nova-premier-v1:0** - Highest capability

## 📝 Usage

1. **Create Dataset**: Upload or generate training data
2. **Build Prompt**: Use the visual prompt builder
3. **Configure Optimization**: Select model, metrics, and parameters
4. **Run Optimization**: Monitor progress in real-time
5. **Review Results**: Compare optimized vs original prompts
6. **Export**: Save optimized prompts for production use

## 🛠️ Development

### Running Tests
```bash
python -m pytest tests/
```

### Database Reset
```bash
rm nova_optimizer.db  # Removes all data
python app.py         # Recreates database
```

### Adding New Features
- **Routes**: Add to `routes/` directory
- **Components**: Add to `components/` directory  
- **Services**: Add to `services/` directory
- **Database**: Extend `database.py` with new tables/methods

## 📚 Documentation

- **Architecture**: See `docs/ARCHITECTURE.md`
- **Features**: See `docs/FEATURES.md`
- **API**: See `docs/README.md`

## 🔒 Security

- All file uploads validated and sanitized
- Database uses parameterized queries
- AWS credentials never stored in database
- Session management with secure tokens

## 🐛 Troubleshooting

### Common Issues
- **Database locked**: Close other instances of the application
- **AWS errors**: Verify credentials and Nova model access
- **Import errors**: Ensure virtual environment is activated
- **Port conflicts**: Change port in `app.py` if 8000 is in use

### Logs
Check the console output for detailed error messages and optimization progress.
