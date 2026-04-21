import pandas as pd
import random
from tqdm import tqdm

# Define the structure
classes = range(1, 6)  # KG is considered as class 0
sections = ['A', 'B', 'C', 'D']
subjects = ['Hindi', 'English', 'Math', 'Bio', 'SST', 'Sc', 'Game', 'Drawing', 'Song']
subject_frequencies = {
    'Hindi': 5, 'English': 5, 'Math': 5,
    'Bio': 4, 'SST': 4, 'Sc': 4,
    'Game': 2, 'Drawing': 2, 'Song': 2
}
# Updated subjects with multiple possible teachers
teachers = {
    'Hindi': ['Anita', 'XYZ'],  # Now a list to allow multiple teachers
    'English': ['Rohan', 'PQR'],
    'Math': ['Priya', 'ABC'],
    'Bio': 'Amit',  # Single teacher subjects remain unchanged
    'SST': 'Vishal',
    'Sc': 'Kavita',
    'Game': ['Rajesh', 'LMN'],  # Example of multiple teachers for other subjects
    'Drawing': 'Sonal',
    'Song': 'Meera'
}

# Function to generate a weekly timetable with 8 periods per day
# Modified function to select a random teacher for subjects with multiple teachers
def generate_weekly_timetable():
    weekly_schedule = {day: [] for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']}
    weekly_subjects = sum([[subject] * freq for subject, freq in subject_frequencies.items()], [])
    random.shuffle(weekly_subjects)

    for day in weekly_schedule:
        while len(weekly_schedule[day]) < 8:
            for subject in list(weekly_subjects):
                if subject not in [subj for subj, _ in weekly_schedule[day]]:
                    # Select a random teacher if there are multiple options
                    teacher = random.choice(teachers[subject]) if isinstance(teachers[subject], list) else teachers[subject]
                    weekly_schedule[day].append((subject, teacher))
                    weekly_subjects.remove(subject)
                    break

    return weekly_schedule

# Generate and write timetables to Excel with progress bar
writer = pd.ExcelWriter('Class_Timetables_8_Periods_Multiple_Teachers.xlsx', engine='openpyxl')
for cls in tqdm(classes, desc="Generating timetables"):
    for section in sections:
        class_section = f"Class {cls} Section {section}"
        timetable = generate_weekly_timetable()
        # Convert timetable to a more suitable format for DataFrame creation
        timetable_df_data = {day: [f"{subject} ({teacher})" for subject, teacher in periods] for day, periods in timetable.items()}
        df_timetable = pd.DataFrame(timetable_df_data).transpose()
        df_timetable.columns = [f'Period {i+1}' for i in range(8)]
        df_timetable.to_excel(writer, sheet_name=class_section)

writer.close()
print("The timetables have been successfully saved to 'Class_Timetables_8_Periods_Multiple_Teachers.xlsx'")