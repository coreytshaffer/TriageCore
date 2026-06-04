def get_fibonacci(n):
    if n <= 0:
        return []
    elif n == 1:
        return [0]
    elif n == 2:
        return [0, 1]
    
    # Recursive step to get sequence up to n-1, then calculate the nth element
    seq = get_fibonacci(n - 1)
    seq.append(seq[-1] + seq[-2])
    return seq

if __name__ == "__main__":
    fib_15 = get_fibonacci(15)
    print("The first 15 numbers of the Fibonacci sequence are:")
    print(fib_15)
