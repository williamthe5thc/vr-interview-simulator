/// The jobs the title screen offers. Ids must match JOB_CATALOG in the server's scenarios/job_interview.py.
public static class InterviewJobs
{
    public readonly struct Job
    {
        public readonly string Id, Label, Company;
        public Job(string id, string label, string company) { Id = id; Label = label; Company = company; }
    }

    public static readonly Job[] All =
    {
        new Job("software_engineer", "Software Engineer", "Nimbus Labs"),
        new Job("customer_service", "Customer Service", "Harbor Telecom"),
        new Job("retail_associate", "Retail Associate", "Maple & Main Market"),
        new Job("restaurant_server", "Restaurant Server", "Copper Table Bistro"),
        new Job("nurse", "Registered Nurse", "Riverside Medical Center"),
        new Job("speech_therapist", "Speech Therapist", "Brightwater Therapy Center"),
        new Job("teacher", "Teacher", "Lakeview Academy"),
    };
}
