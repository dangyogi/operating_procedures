select w1.text, w2.text, count(*)
  from opp_wordref r1
              inner join opp_wordref r2 
                 on r1.paragraph_id = r2.paragraph_id
                    and r1.sentence_number = r2.sentence_number
                    and r1.word_number + 1 = r2.word_number
              inner join opp_word w1 
                 on r1.word_id = w1.id
              inner join opp_word w2
                 on r2.word_id = w2.id
 where w1.text not in
('a', 'ad', 'add', 'af', 'age', 'aid', 'air', 'all', 'an', 'and', 'ann', 'any', 'are',
'as', 'ask', 'at', 'b', 'bad', 'bar', 'be', 'but', 'by', 'c', 'can', 'cd', 'ch', 'co',
'com', 'cp', 'd', 'did', 'do', 'dry', 'e', 'f', 'fac', 'few', 'for', 'fs', 'g', 'go',
'h', 'had', 'has', 'he', 'her', 'him', 'his', 'how', 'i', 'if', 'ii', 'in', 'inc', 'is',
'it', 'its', 'j', 'k', 'l', 'lay', 'lie', 'lsc', 'm', 'map', 'may', 'me', 'met', 'mr',
'n', 'net', 'no', 'non', 'nor', 'not', 'now', 'o', 'of', 'off', 'old', 'on', 'one',
'opt', 'or', 'out', 'p', 'par', 'pet', 'pro', 'r', 're', 'rom', 's', 'see', 'set',
'she', 'six', 'so', 'spa', 'sub', 'sum', 'ten', 'the', 'tie', 'to', 'too', 'two', 'u',
'up', 'use', 'vi', 'via', 'was', 'way', 'we', 'web', 'who', 'www', 'yes', 'yet', 'you')

   and w2.text not in
('a', 'ad', 'add', 'af', 'age', 'aid', 'air', 'all', 'an', 'and', 'ann', 'any', 'are',
'as', 'ask', 'at', 'b', 'bad', 'bar', 'be', 'but', 'by', 'c', 'can', 'cd', 'ch', 'co',
'com', 'cp', 'd', 'did', 'do', 'dry', 'e', 'f', 'fac', 'few', 'for', 'fs', 'g', 'go',
'h', 'had', 'has', 'he', 'her', 'him', 'his', 'how', 'i', 'if', 'ii', 'in', 'inc', 'is',
'it', 'its', 'j', 'k', 'l', 'lay', 'lie', 'lsc', 'm', 'map', 'may', 'me', 'met', 'mr',
'n', 'net', 'no', 'non', 'nor', 'not', 'now', 'o', 'of', 'off', 'old', 'on', 'one',
'opt', 'or', 'out', 'p', 'par', 'pet', 'pro', 'r', 're', 'rom', 's', 'see', 'set',
'she', 'six', 'so', 'spa', 'sub', 'sum', 'ten', 'the', 'tie', 'to', 'too', 'two', 'u',
'up', 'use', 'vi', 'via', 'was', 'way', 'we', 'web', 'who', 'www', 'yes', 'yet', 'you')
 group by w1.text, w2.text having count(*) > 2
 order by 3;
