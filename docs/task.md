## Context

Attached are two notebooks from a PoC phase:
* daily_product_demand_forecast.ipynb
* daily_product_demand_inference.ipynb
 
Take these PoC notebooks and show us how you would turn them into a reliable, production-ready system. 
 
## To do 
1. Refactor the Code 
 
Turn the notebook code into clean, maintainable, and testable code tailored for either AWS or Databricks. You have full freedom here: keep them as clean modular notebooks, extract them into Python packages/scripts, or use a mix. Pick whatever you consider best practice.
Don't worry about tuning ML models or hyperparameter optimization - focus on software craftsmanship (modularity, error handling, config, basic tests).
Using AI tools (Copilot, ChatGPT, etc.) is totally welcome, just make sure you understand and can explain your choices. 
 
2. Solution Design (High-Level) 
 
Propose a simple, production-ready architecture (AWS or Databricks) where: 
 
* Predictions are calculated once a day.
* External clients can query those predictions at any time with low latency.
* The system runs as autonomously as possible with minimal manual intervention. 
 
Keep it high-level, no need to write terraform scripts or deep configs. A rough diagram (Mermaid, draw.io, PNG, etc.) and a few paragraphs explaining your choices will do the trick. 
 
## What to submit: 
 
* A repo link or ZIP with your refactored code.
* Your diagram and brief architecture notes.
