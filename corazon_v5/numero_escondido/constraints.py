"""Pure integer constraint checker. No game rules or network effects."""
def digits(number):return list(map(int,str(abs(number))))
def matches(number,condition):
 kind,*values=condition
 if kind=='greater':return number>values[0]
 if kind=='less':return number<values[0]
 if kind=='range':return values[0]<=number<=values[1]
 if kind=='parity':return number%2==values[0]
 if kind=='multiple':return number%values[0]==0
 if kind=='remainder':return number%values[0]==values[1]
 if kind=='digit_sum':return sum(digits(number))==values[0]
 if kind=='digit':return len(digits(number))>values[0] and digits(number)[values[0]]==values[1]
 if kind=='distinct':return len(set(digits(number)))==len(digits(number))
 if kind=='ascending':return all(a<b for a,b in zip(digits(number),digits(number)[1:]))
 if kind=='descending':return all(a>b for a,b in zip(digits(number),digits(number)[1:]))
 if kind=='digit_delta':return len(digits(number))>max(values[0],values[1]) and digits(number)[values[0]]-digits(number)[values[1]]==values[2]
 if kind=='palindrome':return str(number)==str(number)[::-1]
 raise ValueError(kind)
def solutions(low,high,conditions):
 if type(low)!=int or type(high)!=int or low>high or high-low>1000000:raise ValueError('Invalid domain')
 return [number for number in range(low,high+1)if all(matches(number,c)for c in conditions)]
def validate(puzzle):
 answer=puzzle['answer'];domain=puzzle['domain'];found=solutions(*domain,puzzle['conditions'])
 if found!=[answer]:raise ValueError((puzzle.get('id'),found))
 return True
