list1 = [(1, 2), (3, 4), (5, 6)]
print(len(list1))
for i in range(len(list1)):
    if i == 1:
        print(list1[i])
        list1[i] = (8, 9)
print(list1)