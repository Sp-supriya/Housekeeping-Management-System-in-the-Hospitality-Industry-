from datetime import datetime, timedelta
from enum import Enum
import sqlite3
import random
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, HTML

class RoomStatus(Enum):
    VACANT_CLEAN = "Vacant Clean"
    VACANT_DIRTY = "Vacant Dirty"
    OCCUPIED_CLEAN = "Occupied Clean"
    OCCUPIED_DIRTY = "Occupied Dirty"
    OUT_OF_ORDER = "Out of Order"
    DUE_OUT = "Due Out"

class Priority(Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

class HousekeepingSystem:
    def __init__(self, db_name=":memory:"):  # Using in-memory database for Colab compatibility
        self.conn = sqlite3.connect(db_name)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()

        # Enhanced Rooms table with more fields
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            room_number TEXT PRIMARY KEY,
            room_type TEXT,
            status TEXT,
            last_cleaned DATETIME,
            floor INTEGER,
            max_occupancy INTEGER,
            rate FLOAT,
            notes TEXT,
            maintenance_status TEXT
        )''')

        # Enhanced Staff table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY,
            name TEXT,
            position TEXT,
            shift TEXT,
            contact TEXT,
            hiring_date DATE,
            performance_rating FLOAT,
            rooms_cleaned_today INTEGER DEFAULT 0,
            available BOOLEAN DEFAULT 1
        )''')

        # Enhanced Assignments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY,
            room_number TEXT,
            staff_id INTEGER,
            assignment_date DATE,
            start_time DATETIME,
            end_time DATETIME,
            status TEXT,
            priority TEXT,
            cleaning_duration INTEGER,
            quality_check_passed BOOLEAN,
            FOREIGN KEY (room_number) REFERENCES rooms (room_number),
            FOREIGN KEY (staff_id) REFERENCES staff (id)
        )''')

        # Enhanced Inventory table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY,
            item_name TEXT,
            quantity INTEGER,
            reorder_level INTEGER,
            last_restocked DATE,
            unit_cost FLOAT,
            supplier TEXT,
            category TEXT,
            minimum_order_quantity INTEGER
        )''')

        # New Guest Requests table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS guest_requests (
            id INTEGER PRIMARY KEY,
            room_number TEXT,
            request_type TEXT,
            request_time DATETIME,
            status TEXT,
            priority TEXT,
            notes TEXT,
            assigned_staff_id INTEGER,
            completion_time DATETIME,
            FOREIGN KEY (room_number) REFERENCES rooms (room_number),
            FOREIGN KEY (assigned_staff_id) REFERENCES staff (id)
        )''')

        self.conn.commit()

    def add_room(self, room_number, room_type, floor, max_occupancy, rate, status=RoomStatus.VACANT_CLEAN.value):
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT INTO rooms (room_number, room_type, status, last_cleaned, floor, max_occupancy, rate, maintenance_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (room_number, room_type, status, datetime.now(), floor, max_occupancy, rate, "Good"))
        self.conn.commit()

    def update_room_status(self, room_number, new_status):
        """Update the status of a room"""
        cursor = self.conn.cursor()
        if isinstance(new_status, RoomStatus):
            status_value = new_status.value
        else:
            status_value = new_status

        cursor.execute('''
        UPDATE rooms
        SET status = ?,
            last_cleaned = CASE
                WHEN ? IN (?, ?) THEN DATETIME('now')
                ELSE last_cleaned
            END
        WHERE room_number = ?
        ''', (status_value, status_value,
              RoomStatus.VACANT_CLEAN.value,
              RoomStatus.OCCUPIED_CLEAN.value,
              room_number))
        self.conn.commit()

    def add_guest_request(self, room_number, request_type, priority, notes=""):
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT INTO guest_requests (room_number, request_type, request_time, status, priority, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (room_number, request_type, datetime.now(), "Pending", priority, notes))
        self.conn.commit()

    def update_staff_performance(self, staff_id, performance_rating):
        cursor = self.conn.cursor()
        cursor.execute('''
        UPDATE staff
        SET performance_rating = ?,
            rooms_cleaned_today = rooms_cleaned_today + 1
        WHERE id = ?
        ''', (performance_rating, staff_id))
        self.conn.commit()

    def create_assignment(self, room_number, staff_id, priority=Priority.MEDIUM.value):
        """Create a new cleaning assignment"""
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT INTO assignments (
            room_number, staff_id, assignment_date, start_time,
            status, priority, cleaning_duration, quality_check_passed
        )
        VALUES (?, ?, DATE('now'), DATETIME('now'), ?, ?, 0, 0)
        ''', (room_number, staff_id, "Pending", priority))
        self.conn.commit()

    def get_current_shift(self):
        """Determine current shift based on time of day"""
        hour = datetime.now().hour
        if 7 <= hour < 15:
            return "Morning"
        elif 15 <= hour < 23:
            return "Evening"
        else:
            return "Night"

    def visualize_room_status(self):
        """Generate a pie chart of room statuses"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT status, COUNT(*) FROM rooms GROUP BY status')
        data = cursor.fetchall()

        if not data:  # Check if there's data to visualize
            print("No room data available to visualize")
            return

        labels = [status for status, _ in data]
        sizes = [count for _, count in data]

        plt.figure(figsize=(10, 8))
        plt.pie(sizes, labels=labels, autopct='%1.1f%%')
        plt.title('Room Status Distribution')
        plt.axis('equal')
        plt.show()

    def generate_staff_performance_report(self):
        """Generate a performance report for all staff members"""
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT
            s.name,
            s.position,
            s.performance_rating,
            s.rooms_cleaned_today,
            COUNT(a.id) as total_assignments,
            AVG(a.cleaning_duration) as avg_cleaning_time
        FROM staff s
        LEFT JOIN assignments a ON s.id = a.staff_id
        GROUP BY s.id
        ''')

        data = cursor.fetchall()
        if not data:  # Check if there's data to display
            print("No staff data available")
            return None

        columns = ['Name', 'Position', 'Performance Rating', 'Rooms Cleaned Today',
                  'Total Assignments', 'Average Cleaning Time (min)']
        df = pd.DataFrame(data, columns=columns)
        display(HTML(df.to_html(index=False)))
        return df

    def smart_assignment_algorithm(self):
        """Advanced algorithm for assigning rooms based on multiple factors"""
        cursor = self.conn.cursor()

        # Get available staff with their performance metrics
        cursor.execute('''
        SELECT id, performance_rating, rooms_cleaned_today
        FROM staff
        WHERE available = 1 AND shift = ?
        ''', (self.get_current_shift(),))
        available_staff = cursor.fetchall()

        # Get rooms needing cleaning with priority factors
        cursor.execute('''
        SELECT room_number, status, floor
        FROM rooms
        WHERE status IN (?, ?, ?)
        ''', (RoomStatus.VACANT_DIRTY.value,
              RoomStatus.OCCUPIED_DIRTY.value,
              RoomStatus.DUE_OUT.value))
        dirty_rooms = cursor.fetchall()

        if not available_staff or not dirty_rooms:
            return []

        assignments = []
        for room in dirty_rooms:
            if not available_staff:
                break

            # Calculate priority score for each staff member
            staff_scores = []
            for staff in available_staff:
                staff_id, performance, rooms_cleaned = staff
                score = (performance * 0.4 +  # 40% weight to performance
                        (1 - (rooms_cleaned / 10)) * 0.6)  # 60% weight to workload
                staff_scores.append((staff_id, score))

            # Assign to staff member with highest score
            best_staff = max(staff_scores, key=lambda x: x[1])
            priority = Priority.HIGH.value if room[1] == RoomStatus.DUE_OUT.value else Priority.MEDIUM.value

            self.create_assignment(room[0], best_staff[0], priority)
            assignments.append((room[0], best_staff[0]))

            # Update staff workload
            available_staff = [s for s in available_staff if s[0] != best_staff[0]]

        return assignments

    def generate_inventory_report(self):
        """Generate a detailed inventory report with reorder recommendations"""
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT
            item_name,
            quantity,
            reorder_level,
            unit_cost,
            supplier,
            category,
            CASE
                WHEN quantity <= reorder_level THEN 'Reorder Required'
                WHEN quantity <= reorder_level * 1.2 THEN 'Low Stock'
                ELSE 'Adequate Stock'
            END as stock_status
        FROM inventory
        ORDER BY stock_status DESC
        ''')

        data = cursor.fetchall()
        if not data:  # Check if there's data to display
            print("No inventory data available")
            return None

        columns = ['Item Name', 'Quantity', 'Reorder Level', 'Unit Cost',
                  'Supplier', 'Category', 'Stock Status']
        df = pd.DataFrame(data, columns=columns)
        display(HTML(df.to_html(index=False)))
        return df

    def close_connection(self):
        self.conn.close()

# Example usage for Google Colab
def main():
    # Create system instance
    system = HousekeepingSystem()

    # Add sample rooms
    system.add_room("101", "Single", 1, 2, 100.0)
    system.add_room("102", "Double", 1, 4, 150.0)
    system.add_room("201", "Suite", 2, 4, 250.0)

    # Add sample staff
    cursor = system.conn.cursor()
    cursor.execute('''
    INSERT INTO staff (name, position, shift, contact, hiring_date, performance_rating)
    VALUES
        ("John Doe", "Housekeeper", "Morning", "555-0101", "2023-01-01", 4.5),
        ("Jane Smith", "Supervisor", "Morning", "555-0102", "2023-02-01", 4.8),
        ("Mike Johnson", "Housekeeper", "Evening", "555-0103", "2023-03-01", 4.2)
    ''')
    system.conn.commit()

    # Add sample inventory
    cursor.execute('''
    INSERT INTO inventory (item_name, quantity, reorder_level, unit_cost, supplier, category, minimum_order_quantity)
    VALUES
        ("Towels", 100, 50, 5.99, "LinenCo", "Linens", 50),
        ("Toiletries", 200, 100, 2.99, "SupplyCo", "Amenities", 100),
        ("Cleaning Solution", 50, 30, 8.99, "CleanCo", "Cleaning", 20)
    ''')
    system.conn.commit()

    # Update some room statuses
    system.update_room_status("101", RoomStatus.OCCUPIED_DIRTY)
    system.update_room_status("102", RoomStatus.DUE_OUT)

    # Generate and display reports
    print("\nRoom Status Distribution:")
    system.visualize_room_status()

    print("\nStaff Performance Report:")
    system.generate_staff_performance_report()

    print("\nInventory Report:")
    system.generate_inventory_report()

    # Run smart assignment algorithm
    print("\nGenerating Smart Assignments...")
    assignments = system.smart_assignment_algorithm()
    for room, staff in assignments:
        print(f"Room {room} assigned to staff ID {staff}")

    system.close_connection()

if __name__ == "__main__":
    main()
