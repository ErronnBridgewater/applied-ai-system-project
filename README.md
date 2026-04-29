Original Project: PawPal+

Summary: PawPal+ is an intelligent assistant built in Python to track the user's pet care activities like feeding, walking, and grooming. It is designed to manage multi-pet households. in a chronological queue. By leveraging an Agentic Workflow, it not only lists tasks but also analyzes pet health, owner energy levels, and time constraints to generate a realistic, optimized schedule that prioritizes the wellbeing of the pet. 

Archiecture Overview:

1. Human Input: Users define pets, owners, and specific care tasks via the Streamlit UI.

2. The Scheduler: Acts as the central orchestrator, holding the state of the task queue.

3. AIAgent (Gemini): The Scheduler sends the context to the AI Agent (powered by Gemini 2.5 Flash), which "reasons" through priorities.

4. Validate & Refine: The system programmatically checks the AI's plan against hard constraints (like the owner's total time budget) and refines the list if necessary.

5. Output: A finalized schedule is presented for human review and is aware of any conflicts.

Setup Instructions:
1. Clone the Repository: 
    git clone https://github.com/ErronnBridgewater/ai110-module2show-pawpal-starter.git cd ai110-module2show-pawpal-starter

2. Install Dependencies:
   pip install streamlit google-generativeai python-dotenv

3. Environment Setup:
    - Create a file named api_key.env in the root directory.
    - Add your own Gemini API Key: GEMINI_API_KEY=your_key_here

4. Launch the App:
   streamlit run app.py

Sample Interations: 
Example 1
Input: Two tasks added at the same time: "Monthly Nail Trim" (Priority 1) and "Emergency Heart Meds" (Priority 3).
AI Output: ✅ Emergency Heart Meds (22 mins)
           ✅ Monthly Daily Trim (20 mins)
           Time conflict (same pet): Monthly Daily Trim (Mochi) overlaps with Emergency Heart Meds (Mochi)

Example 2
Input: Tasks totaling 300 minutes (e.g., a long hike, grooming, and training). The system has a hardcoded owner budget of 4 hours (240 minutes).
System Output: Duration value must be less or equal to 240. 


Design Decisions: 
I used python @dataclasses to make sure that there were easy data manipulation between the frontend and the AI backend. To prevent the application from crashing due to AI "conversational filler," I implemented a custom JSON cleaner to isolate the raw task list from the LLM response. I chose to separate the AI's reasoning logic from its validation logic. The AI suggests the order, but the Python script checks for time conflicts so the schedule is realistically possible. 

Testing Summary:

What worked: The integration of google-generativeai allowed for sophisticated task prioritization that simple sorting couldn't achieve (e.g., understanding that "Health" is inherently more important than "Grooming").
Initial challenges: I initially faced errors due to the deprecation of Gemini 1.5 models. Upgrading to the Gemini 2.5 series and handling JSON parsing errors (Line 1, Column 1) significantly improved the system's reliability.
What I learned: AI isn't perfect at formatting. Building "guardrails" in the code is essential for bridging the gap between creative AI responses and strict software requirements.
Testing Results: "9 out of 10 scheduling scenarios passed; the system successfully caught and flagged time-budget overruns in 100% of test cases. Reliability improved significantly after implementing the JSON sanitization layer."

Reflection: This project taught me that Agentic AI is most powerful when it is used as a collaborator rather than a solution generator. By combining the AI's ability to "reason" about pet care with Python’s ability to enforce "hard rules" (like time and logic), I created a system that is both smart and reliable. This experience has deepened my understanding of how to build AI-native applications that solve real-world problems.

Loom walkthrough: [Watch the Loom video](https://www.loom.com/share/0ec704f79cf144228a2195c4acfdfe03)