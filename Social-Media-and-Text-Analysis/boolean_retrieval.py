def intersect_postings(p1, p2):
    """
    Finds the intersection (AND) of two sorted postings lists using a two-pointer approach.
    
    Args:
    p1 (list): First sorted list of document IDs.
    p2 (list): Second sorted list of document IDs.
    
    Returns:
    list: A list containing document IDs present in both p1 and p2.
    """
    answer = []
    i = 0  # Pointer for p1
    j = 0  # Pointer for p2
    
    # Loop until one of the pointers reaches the end of its list
    while i < len(p1) and j < len(p2):
        if p1[i] == p2[j]:
            # Both docIDs match! Add to our answer and move both pointers forward.
            answer.append(p1[i])
            i += 1
            j += 1
        elif p1[i] < p2[j]:
            # The docID in p1 is smaller, so move the p1 pointer forward to catch up.
            i += 1
        else:
            # The docID in p2 is smaller, so move the p2 pointer forward to catch up.
            j += 1
            
    return answer

if __name__ == "__main__":
    # Example lists (must be sorted!)
    brutus_postings = [1, 2, 54, 789]
    caesar_postings = [1, 3, 4, 678]
    calpurnia_postings = [2, 31, 54, 101]

    print("--- Boolean Retrieval AND Query Example ---")
    
    # 1. brutus AND caesar
    res1 = intersect_postings(brutus_postings, caesar_postings)
    print(f"brutus AND caesar       -> Documents: {res1}")

    # 2. brutus AND calpurnia
    res2 = intersect_postings(brutus_postings, calpurnia_postings)
    print(f"brutus AND calpurnia    -> Documents: {res2}")
