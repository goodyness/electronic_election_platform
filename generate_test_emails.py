import csv

def generate_emails(filename, count):
    print(f"Generating {count} emails into {filename}...")
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['email']) # Optional header
        for i in range(1, count + 1):
            writer.writerow([f'student{str(i).zfill(5)}@testuni.edu.ng'])
    print("Done!")

if __name__ == '__main__':
    generate_emails('test_emails.csv', 10000)