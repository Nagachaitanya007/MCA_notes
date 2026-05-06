---
title: The Saga Pattern: Handling Failures via Compensating Transactions
date: 2026-05-06T04:46:21.350120
---

# The Saga Pattern: Handling Failures via Compensating Transactions

1. 💡 **The "Big Picture" (Plain English):**
   - **What is it?** In a distributed system, you can’t use a single "Undo" button (like a database rollback) because different services own different databases. The Saga Pattern is a sequence of local transactions where each step has a corresponding "undo" action if something goes wrong later.
   - **Real-world analogy:** Think of booking a vacation. 
     1. You book a **Flight**. 
     2. You book a **Hotel**. 
     3. You try to book a **Rental Car**, but they are sold out.
     Since you can't go without a car, you have to call the hotel and the airline to cancel. You don't just "delete" the records; you issue a cancellation that might involve a refund fee. That cancellation is a **Compensating Transaction**.
   - **Why care?** In a microservices world, business processes span multiple services. If Step 3 fails, Step 1 and 2 are already "committed" to their databases. Without a Saga, your system ends up in a "zombie state" (money taken, but no vacation booked).

2. 🛠️ **How it Works (Step-by-Step):**
   - **Step 1:** Service A performs a local transaction (e.g., Reserve Credit).
   - **Step 2:** Service B performs a local transaction (e.g., Book Flight).
   - **Step 3:** Service C fails (e.g., Hotel Full).
   - **Step 4 (The Magic):** The system triggers "Compensating Transactions" in reverse order: Service B cancels the flight, then Service A releases the credit.

**Clean Code Snippet (Orchestration Style):**
```python
class TravelSagaOrchestrator:
    def execute(self, trip_details):
        # Step 1: Book Flight
        flight_id = flight_service.book(trip_details)
        if not flight_id:
            return "Failed at start"

        # Step 2: Book Hotel
        hotel_id = hotel_service.book(trip_details)
        if not hotel_id:
            # FAILURE! Start Compensation
            flight_service.cancel_booking(flight_id)
            return "Rolled back flight"

        # Step 3: Book Car
        car_id = car_service.book(trip_details)
        if not car_id:
            # FAILURE! Start Compensation in reverse
            hotel_service.cancel_booking(hotel_id)
            flight_service.cancel_booking(flight_id)
            return "Rolled back hotel and flight"

        return "Success!"
```

**Flow Diagram:**
```text
SUCCESS PATH:
[Start] -> (Book Flight) -> (Book Hotel) -> (Book Car) -> [Finish]

FAILURE AT HOTEL:
[Start] -> (Book Flight) -> (Book Hotel FAIL!) 
                                |
          (Cancel Flight) <-----+
                |
             [Exit]
```

3. 🧠 **The "Deep Dive" (For the Interview):**
   - **Orchestration vs. Choreography:** 
     - *Orchestration:* A central "brain" tells everyone what to do. Easier to debug but creates a central point of failure.
     - *Choreography:* Each service publishes an event (e.g., "FlightBooked"), and the next service listens for it. This is highly decoupled but can become "spaghetti" where it's hard to see the whole process.
   - **Trade-offs:** 
     - **Complexity:** You have to write twice as much code (the action + the compensation).
     - **Lack of Isolation:** This is the big one. Other users might see the "booked" flight before it's cancelled. This is called "Eventual Consistency."
   - **Interviewer Probes:**
     - *Probe:* "What happens if the **Compensating Transaction** itself fails?"
       - *Answer:* You need a retry mechanism for compensations. If that fails, you need a "Dead Letter Queue" and human intervention/monitoring. Compensations *must* be idempotent (safe to call multiple times).
     - *Probe:* "How do you handle 'Dirty Reads' in a Saga?"
       - *Answer:* Since Sagas don't have ACID isolation, we use "Semantic Locks" (setting a state to 'PENDING') or "Versioning" to ensure other processes know the data is currently in a transition state.

4. ✅ **Summary Cheat Sheet:**
   - **Takeaway 1:** Distributed systems cannot use standard ACID transactions; use Sagas for long-running business logic.
   - **Takeaway 2:** Every forward action must have a defined failure-path (compensation).
   - **Takeaway 3:** Compensations must be **idempotent**. If the network fails during a "Cancel," you must be able to send the "Cancel" again without breaking anything.
   - **Golden Rule:** "In a distributed world, you don't 'undo'—you 'correct' with a new action."