from typing import Any


class CircularQueue(object):

    # constructor
    def __init__(self, size: int):  # initializing the class
        self.size = size
        # initializing queue with none
        self.queue: list[Any | None] = [None for i in range(size)]
        self.front = self.rear = -1

    def is_full(self):
        return (self.rear + 1) % self.size == self.front

    def is_empty(self):
        return self.front == -1

    def enqueue(self, data) -> bool:
        # condition if queue is full
        if self.is_full():
            # print(" Queue is Full\n")
            return False
        # condition for empty queue
        elif self.front == -1:
            self.front = 0
            self.rear = 0
            self.queue[self.rear] = data
            return True
        else:
            # next position of rear
            self.rear = (self.rear + 1) % self.size
            self.queue[self.rear] = data
            return True

    def dequeue(self) -> Any | None:
        # condition for empty queue
        if self.is_empty():
            # print("Queue is Empty\n")
            return None
        # condition for only one element
        elif self.front == self.rear:
            temp = self.queue[self.front]
            self.front = -1
            self.rear = -1
            return temp
        else:
            temp = self.queue[self.front]
            self.front = (self.front + 1) % self.size
            return temp

    def display(self):
        # condition for empty queue
        if self.is_empty():
            print("Queue is Empty")
        elif self.rear >= self.front:
            print("Elements in the circular queue are:")
            for i in range(self.front, self.rear + 1):
                print(self.queue[i], end=" ")
        else:
            print("Elements in Circular Queue are:", end=" ")
            for i in range(self.front, self.size):
                print(self.queue[i], end=" ")
            for i in range(0, self.rear + 1):
                print(self.queue[i], end=" ")
        if self.is_full():
            print("Queue is Full")
