# PRAVISION — Universal OSINT & Intelligence Platform
> *"See Everything. Connect Everything. Understand Everything."*

**PRAVISION** is a production-quality, Windows-local Universal OSINT and Intelligence platform. It bridges multi-source intelligence gathering, automatic input classification, recursive evidence expansion, cross-platform corroboration, and relationship graph topology into a unified dark-first intelligence workstation.

---

## ⚡ Core Philosophy: ONE INPUT → UNIFIED INTELLIGENCE
The user does not need to memorize dozens of disparate terminal commands or manually orchestrate complex tools:
```
USER INPUT (Username, Email, Phone, Domain, IP, Media, Document, Coords)
   │
   ▼
[Universal Input Classifier] ➔ Detects Entity & Investigation Mode
   │
   ▼
[Concurrent Connector Orchestrator] ➔ Queries Approved Public Sources
   │
   ▼
[Recursive Intelligence Engine] ➔ Expands Discovered Entities with Depth Bounds
   │
   ▼
[Evidence Corroboration & Graph Topology] ➔ Maps Relationships & Scores Confidence
   │
   ▼
[Unified Intelligence Dossier] ➔ Interactive Dark UI + On-Demand Export (HTML / PDF / JSON)
```

---

## 🚀 Quickstart on Windows

### 1. One-Click Launch
Double-click `start_pravision.bat` in the project root:
```cmd
start_pravision.bat
```
This batch script will:
- Set Python encoding to UTF-8 (`chcp 65001`, `PYTHONIOENCODING=utf-8`, `PYTHONUTF8=1`).
- Verify dependencies and Python virtual environment (`venv`).
- Start the FastAPI backend engine on `127.0.0.1:8000`.
- Automatically open the dashboard in your default web browser (`http://127.0.0.1:8000`).

### 2. Manual Environment Setup (Optional)
If running on a fresh workstation:
```powershell
powershell -ExecutionPolicy Bypass -File .\setup_pravision.ps1
```

---

## 🛡️ Privacy & Non-Negotiable Zero-Persistence Mandate
PRAVISION enforces a strict **Zero-Persistence Policy**:
- **No Target History**: Investigation targets and findings are held exclusively in volatile RAM.
- **No Permanent Profile Databases**: Closing or clearing an investigation erases memory state immediately.
- **Automatic Ephemeral Purging**: Uploaded media and temporary ELA forensic difference images are wiped from the runtime directory upon clearing an investigation.
- **Log Redaction**: Sensitive target identifiers (emails, phone numbers, API keys) are sanitized from diagnostic log streams.
- **On-Demand Exports Only**: Intelligence dossiers (HTML, PDF, JSON) are generated only upon explicit user request.

---

## 🧭 Investigation Modes

| Mode | Name | Key Capabilities |
| :--- | :--- | :--- |
| **Mode 1** | Public Identity Intelligence | Sherlock, Maigret, GHunt, SocialScan, public handle mapping |
| **Mode 2** | Media & Document Intelligence | EXIF camera metadata, GPS tags, perceptual hashes, Error Level Analysis (ELA) |
| **Mode 3** | Email Intelligence | MX DNS routing, GHunt Google Gaia discovery, EmailRep, HIBP exposure |
| **Mode 4** | Phone Intelligence | E.164 normalization, international carrier detection, region classification |
| **Mode 5** | Website & Domain Intelligence | Subfinder (CRT.sh), DNSx multi-record resolver, WhatWeb, TLS profiling |
| **Mode 6** | Organization & Asset Intelligence | Passive ASN lookup, Shodan / Censys adapters, Nmap policy guard |
| **Mode 7** | Global Situational Intelligence | OpenSky Network live aircraft ADS-B, USGS Earthquakes, OpenStreetMap |

---

## 🧰 Complete 64-Tool Registry
PRAVISION integrates a complete catalogue across 9 categories. See [CONNECTOR_CATALOGUE.md](file:///C:/Users/hp/OneDrive/Desktop/PRAVISION/CONNECTOR_CATALOGUE.md) for full capability manifests, official repositories, and pre-flight validation status.

### GHunt 2.3.4 (Spider Edition) Integration
- Integrates with the existing Windows executable `C:\Users\hp\.local\bin\ghunt.exe`.
- Utilizes existing session cookies at `~/.malfrats/ghunt/creds.m` without copying credentials into frontend code.
- Resiliently handles Windows UTF-8 console output and People API cover-photo schema updates.

---

## 💻 Technical Architecture
- **Backend**: Python 3.12, FastAPI, Pydantic v2, HTTPX, WebSockets, dnspython, Pillow, ExifRead, ReportLab, pytest.
- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS v4, Lucide React, Leaflet, interactive SVG graph topology.
- **Network**: Binds exclusively to `127.0.0.1` by default.
