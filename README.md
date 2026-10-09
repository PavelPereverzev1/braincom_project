# 🛒 Brain.com.ua E-Commerce Product Scraper & Django Pipeline

A robust, fault-tolerant web scraping and data extraction pipeline for **Brain.com.ua** implemented using three different automation technologies: **`requests` + `BeautifulSoup4`**, **`SeleniumBase` (UC Mode)**, and **`Playwright`**. Collected product details are normalized and persisted into a **PostgreSQL** database via **Django ORM**.

---

## 📋 Task Overview & Scope

The objective of this project is to parse detailed product information from `brain.com.ua`, bypass anti-bot mechanisms (Cloudflare / 403 Forbidden AJAX blocks), and persist normalized records into a PostgreSQL database.

### Key Deliverables:
* **Search & Navigation**: Perform live autocomplete search for `Apple iPhone 15 128GB Black` and navigate to the selected product page.
* **Fault-Tolerant Data Parsing (Safe Extraction)**:
  * Full Product Title & Unique Product Code (SKU)
  * Brand / Vendor, Color, and Storage Memory
  * Screen Specifications (Diagonal & Resolution)
  * Regular Price & Promotional Price (if applicable)
  * Customer Reviews Count
  * List of High-Resolution Image URLs
  * Full Technical Characteristics Dictionary
* **Database Integration**: Save/update records in **PostgreSQL** via **Django ORM** using `update_or_create`.
* **Data Artifacts**: Extracted data and database exports are manually placed in the `results/` directory for analysis.

---

## 🛠 Tech Stack

* **Language**: Python 3.11+
* **Framework**: Django (Core & ORM)
* **Database**: PostgreSQL (Running in Docker)
* **Scraping & Automation Libraries**:
  * `requests` + `BeautifulSoup4` (Fast HTTP parsing)
  * `SeleniumBase` (Undetected-Chromedriver Mode for Cloudflare bypass)
  * `Playwright` (Sync API with anti-detection flags)
* **Containerization**: Docker CLI (PostgreSQL)

---

## 📁 Project Structure

```text
braincom_project/
│
├── braincom_project/          # Django project settings & configuration
│   ├── settings.py
│   └── ...
├── parser_app/                # Django application
│   ├── models.py              # Product model for PostgreSQL
│   └── ...
│
├── modules/                   # Scraper implementations
│   ├── load_django.py         # Django environment loader for standalone scripts
│   ├── 1_parse_requests.py    # Requests + BeautifulSoup implementation
│   ├── 2_parse_selenium.py    # SeleniumBase (UC Mode) implementation
│   └── 3_parse_playwright.py  # Playwright implementation
│
├── results/                   # Directory for manual data exports and output artifacts
├── manage.py                  # Django CLI manager
├── requirements.txt           # Project dependencies
└── README.md                  # Project documentation
```
---

## 🗄 Database Model (`parser_app/models.py`)

    from django.db import models

    class Product(models.Model):
        code = models.CharField(max_length=50, unique=True, verbose_name="Product Code")
        title = models.CharField(max_length=255, verbose_name="Title")
        color = models.CharField(max_length=100, null=True, blank=True)
        memory = models.CharField(max_length=100, null=True, blank=True)
        vendor = models.CharField(max_length=100, null=True, blank=True)
        price_regular = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
        price_promo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
        reviews_count = models.IntegerField(default=0)
        screen_diagonal = models.CharField(max_length=50, null=True, blank=True)
        screen_resolution = models.CharField(max_length=50, null=True, blank=True)
        photos = models.JSONField(default=list)
        characteristics = models.JSONField(default=dict)
        status = models.CharField(max_length=50, default="Done")
        parser_type = models.CharField(max_length=50)  # 'Requests', 'Selenium', or 'Playwright'
        created_at = models.DateTimeField(auto_now_add=True)
        updated_at = models.DateTimeField(auto_now=True)

        def __str__(self):
            return f"[{self.code}] {self.title}"

---

## 🐳 PostgreSQL Database via Docker

The database runs in a standalone Docker PostgreSQL container:

### 1. Create and Run PostgreSQL Container

    docker run --name braincom_pg -e POSTGRES_DB=braincom_db -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -v braincom_pgdata:/var/lib/postgresql -p 5432:5432 -d postgres:latest

### 2. Container Management Commands

* **Check running containers**:
    `docker ps`
* **Start existing container**:
    `docker start braincom_pg`
* **Stop container**:
    `docker stop braincom_pg`

---

### Django Database Configuration (`braincom_project/settings.py`)

Ensure your `settings.py` matches the container settings:

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'braincom_db',
            'USER': 'postgres',
            'PASSWORD': 'postgres',
            'HOST': 'localhost',
            'PORT': '5432',
        }
    }

Apply migrations to initialize the database schema:

    python manage.py migrate

---

## 🚀 Installation & Setup

1. **Clone the Repository & Set Up Virtual Environment**:

    git clone [https://github.com/PavelPereverzev1/braincom_project.git](https://github.com/PavelPereverzev1/braincom_project.git)
    
    cd braincom_project

    python -m venv .venv
    # Windows:
    .venv\Scripts\activate
    # Linux/macOS:
    source .venv/bin/activate

2. **Install Dependencies**:

    pip install --upgrade pip
    pip install -r requirements.txt

    # Install Playwright browser binaries
    playwright install chromium

---

## 🎯 Running the Scrapers

You can execute any of the three scraper modules independently:

### 1. HTTP Requests + BeautifulSoup Scraper
Fastest approach using direct HTTP requests and session management:

    python modules/1_parse_requests.py

### 2. SeleniumBase (UC Mode) Scraper
Bypasses advanced bot protection using Undetected Chromedriver mode:

    python modules/2_parse_selenium.py

### 3. Playwright Scraper
Browser automation with stealth configurations and custom event triggers:

    python modules/3_parse_playwright.py

---

## 📁 Results & Output Handling

Extracted dataset files, JSON snapshots, or manual database exports are stored in the `results/` directory located at the root level alongside the `modules/` folder.

---

## 🛠 Key Architecture Features & Fault Tolerance

1. **Safe Extraction Pattern (`safe_extract`)**: All HTML element parsers are wrapped in safe extraction functions. If an element selector changes or is missing from a product page, default values (`None`, `0`, `[]`) are assigned without halting script execution.
2. **Dynamic UI Race Condition Handling**: Overcomes issues caused by hidden mobile `<h1>` elements and input fields (`display: none`) by targeting specific desktop selectors (`.header-bottom`, `.br-pr-code`, `.br-pr-chr`) and using DOM presence checks (`wait_for_element_present` / `state="attached"`).
3. **Async / Sync Context Separation**: Isolates Playwright event loops from Django ORM database execution, preventing `SynchronousOnlyOperation` exceptions.
4. **AJAX Live-Search Triggering**: Dispatches native JS `input` events after typing to ensure live search dropdowns fire reliably.
