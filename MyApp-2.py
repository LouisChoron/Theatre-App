import streamlit as st
from selenium import webdriver
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
#import time
#from PIL import ImageGrab, Image
import re
#import ast
import string
import matplotlib.pyplot as plt
import json
import datetime
from dateutil.relativedelta import relativedelta
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

st.title('Theatre Time Baby!')


###################################################################################################################### FUNCTIONS
######################################################################################################################
def finddata():
    '''Takes all data from the API availability page'''
    content = driver.page_source
    soup = BeautifulSoup(content)
    tag = soup.body
    data=[]
    for string in tag.strings:
        data.append(string)
    return data

def make_dataframe(data):
    '''Creates a dataframe from the given API page data'''
    convert_data=str(data[0])    #make string

    #put words in speech marks
    output_str1=re.sub(r': \bfalse\b', r': "false"', convert_data)
    output_str1=re.sub(r': \btrue\b', r': "true"', output_str1)
    output_str1=re.sub(r': \bnull\b', r': "null"', output_str1)

    #remove final 2 sentences
    nope=output_str1.split(', "currency":')[0]    #need to split string to remove the very FINAL currency bit, which screws up the whole dataframe process
    #re-add a final } symbol
    nope2=nope+'}'
    #make dictionary/nested dictionary
    #nope3=ast.literal_eval(nope2)
    nope3=json.loads(nope2)

    #make dataframe
    dataframe=pd.concat({k: pd.DataFrame(v).T for k, v in nope3.items()}, axis=0)
    return dataframe

def split_dataframe(dataframe):
    '''Splits our single large dataframe into the legend,seats and seat_block sections for easier reading'''
    legend1 = dataframe.drop(["seats","seat_blocks"], axis=0)   ##@@@@@@@ IMPORTANT axis 1 is column, axis 0 is row!!
    legend_df = legend1.drop(columns=legend1.columns[-13:],axis=1) 

    seats1 = dataframe.drop(["legend","seat_blocks"], axis=0)   ##@@@@@@@ IMPORTANT axis 1 is column, axis 0 is row!!
    seats2 = seats1.drop(columns=seats1.columns[-7:],axis=1)
    seats_df = seats2.drop(columns=seats2.iloc[:, :seats2.columns.get_loc('legend')].columns.tolist()) #general(drop up to legend) 

    seat_blocks1 = dataframe.drop(["legend","seats"], axis=0)   ##@@@@@@@ IMPORTANT axis 1 is column, axis 0 is row!!
    seat_blocks_df = seat_blocks1.drop(columns=seat_blocks1.iloc[:, :seat_blocks1.columns.get_loc('length')].columns.tolist()) #general(drop up to legend) 
    
    return legend_df,seats_df,seat_blocks_df

def improved_seats_df(legend_df,seats_df,seat_blocks_df,daterow):
    '''Replaces legend column in seats_df with their respective prices,
    and seat_block column with the seat description (stalls etc). Also 
    adds date/time of perf to each seat!'''
    
    seats_df1=seats_df
    for i in range(len(legend_df.columns)):   #only for possible legend references (0-7 etc) as replace replaces ALL in dataframe
        legend_val=legend_df.iloc[6][i]
        seats_df1['legend']=seats_df1['legend'].replace(i,legend_val)

    seats_df2=seats_df1
    #instead of massive loop here, the line profiling helped identify it was slow and so we replaced!
    seat_blocks_df_reindexed=seat_blocks_df.reset_index()
    seats_df2['seat_block'] = seats_df2['seat_block'].map(seat_blocks_df_reindexed.set_index('level_1')['desc'])

    seats_df3=seats_df2
    seats_df3['Date']=daterow[2]
    seats_df3['Time']=daterow[0]

    return seats_df3

def make_month_perfs_df(data):
    '''For given data, makes a dataframe with the dates/times/ID of each performance within that month'''
    convert_data=str(data[0])    #make string

    #put words in speech marks
    output_str1=re.sub(r': \bfalse\b', r': "false"', convert_data)
    output_str1=re.sub(r': \btrue\b', r': "true"', output_str1)
    output_str1=re.sub(r': \bnull\b', r': "null"', output_str1)

    #split off final section
    nope=output_str1.split('}, "min_combined":')[0]
    nope2=nope+'}}}}}}'
    nope3=json.loads(nope2)

    #make dataframe
    dataframe=pd.json_normalize(nope3)
    dataframe2=dataframe.T
    new_df=dataframe2.iloc[::5, :]    #keeps only every 5th row
    new_df_2= new_df.reset_index(level=0)   #makes index column into new column
    new_df_3=new_df_2.explode(0)     #splits elements which are lists of 2 perfs, into 2 rows!
    B=pd.DataFrame(new_df_3[0].tolist(),index=new_df_3.index) #splits each dict value to diff columns, keeps correct index
    C=B.reset_index()
    D=C[['index', 'time','perf_id']]   #keeps only required columns

    X=new_df_3['index'].str.split('.', expand=True)   #split index of other df to get years/months/day bit
    Y=X.reset_index()
    
    D=pd.concat([D, Y], axis=1, join='inner')   #combine years/months/day df with time/ID df
    E=D.drop(columns=['index',0,2,4,6])   #removing unecessary columns
    F = E.reset_index(drop=True)
    return F

def PerfDates(start,end):
    #removing 'day' (not needed here as we search in whole months, just used to include day in overall function) 
    #and replacing with 01, to search months (below) from their start day
    start2=(start[:-2])+'01'
    end2=(end[:-2])+'01'
    MonthRange=pd.to_datetime([start2, end2])

    perf_data_urls=[]
    for i in MonthRange:
        date=str(i)[0:10]
        perf_data_urls.append('https://tickets.wickedthemusical.co.uk/api/calendar/1DU1L/?start_date='+date)
    return perf_data_urls


def PerfURLS(start_day,end_day):
    
    perfs=PerfDates(start_day, end_day)     # urls to find perf date data from (E.G 16th -> 2.30pm...17th etc)

    for i in range(len(perfs)):
        driver.get(perfs[i])     #looking through each of these urls
        data=finddata()
        month_perfs=make_month_perfs_df(data)    #creating month_perfs df per month...then appending below!
        if i ==0:
            all_perfs=month_perfs     #for first appending, note all perfs has ALL perfs in months
        else:
            all_perfs=pd.concat([all_perfs,month_perfs])     #appending new dataframe to total/cumulative df

        #this code (as below) causes urls to open in new TABS not WINDOWS
        if(i!=len(perfs)-1):
                driver.execute_script("window.open('');")
                chwd = driver.window_handles
                driver.switch_to.window(chwd[-1])

    print('All Months Checked')
    driver.quit()
    
    ########################## cutting out rows to allow for single days
    
    #making sure each month and day number has 2 digits (so when using big numbers later, keep place value)
    all_perfs[3] = all_perfs[3].apply('{0:0>2}'.format)
    all_perfs[5] = all_perfs[5].apply('{0:0>2}'.format)

    #Making useful columns
    all_perfs['Date'] = all_perfs[1].astype(str) + '-' + all_perfs[3].astype(str) + '-' + all_perfs[5].astype(str)
    all_perfs['Number'] = (all_perfs[1]) + (all_perfs[3]) + (all_perfs[5])
    all_perfs['Number'] = pd.to_numeric(all_perfs['Number'])               #making integers
    all_perfs=all_perfs.drop([1,3,5],axis = 1)

    #Day specific
    start_number = int(re.sub('-','',start_day))    #creating full numbers (for searching within column) and making integers
    end_number = int(re.sub('-','',end_day))

    #selecting only perfs within date range (USES DAY here)
    all_perfs = all_perfs[(all_perfs['Number'] >= start_number) & (all_perfs['Number'] <= end_number)]
    all_perfs.drop_duplicates(inplace=True)     # removing duplicates
    #display(all_perfs)
    ###########################

    perf_id = all_perfs['perf_id'].tolist()    #taking the perf_ids from all_perfs df
    urls=[]
    ## EACH API AVAILABILITY URL
    for i in perf_id:
        Split=(i.split('-'))[0]
        urls.append("https://tickets.wickedthemusical.co.uk/api/availability/"f'{Split}'"/"f'{i}'"/0/?seat_selection=true")

    return urls,all_perfs

def scrape_data(urls):
    ## Found this code (the if loop) online to open multiple tabs
    total=[]
    k=0
    for i in range(len(urls)):
        driver.get(urls[i])
        data=finddata()
        df_j=make_dataframe(data)
        legend_df_j,seats_df_j,seat_blocks_df_j = split_dataframe(df_j)

        #Adding the following date feature has REALLY killed the speed
        daterow=all_perfs.iloc[k].values.tolist()  #takes single row from all_perfs df (time,date,number etc) to be included into seats df
        seats_df_2_j=improved_seats_df(legend_df_j,seats_df_j,seat_blocks_df_j,daterow)
        k=k+1
        total.append(seats_df_2_j)

        if(i!=len(urls)-1):
            driver.execute_script("window.open('');")
            chwd = driver.window_handles
            driver.switch_to.window(chwd[0])
            driver.close()
            driver.switch_to.window(chwd[-1])

    print('All Dates Checked')
    driver.quit()
    print('Web Session Closed')

    #This code is an absolute god-send, this finds the cheapest seats...in 3 lines!!
    total_df = pd.concat(total)   #create total dataframe
    total_df_sorted = total_df.sort_values(by=['seat_id','seat_block','legend'],na_position='last')  #order seats by id, then block, then by their ascending prices
    total_df_cheapest = total_df_sorted.drop_duplicates(subset=['seat_id','seat_block'], keep='first').reset_index()  #takes cheapest seat (which is top) relative to legend
    #display(total_df_cheapest)
    #display(total_df)
    return(total_df,total_df_cheapest)

def pricerange(Low,High,df):
    Low=float(Low)
    High=float(High)   #ensuring floats, was an issue with app!
    df['Low']=Low
    df['High']=High
    available_df = df.query('Low <= legend <= High')
    return(available_df)

######## filtering adjacent seats
#Firstly fixing a future problem, that B9 sorts AFTER B10...so making all 2-digits into 3 by adding middle 0  (super important!)
#Similar issue again with ZB40's sorting before ZB5
def correct_sort(total_df_filter):
    two_to_three=[]
    for i in total_df_filter.loc[total_df_filter.seat_id.str.len()==2, 'seat_id']:    #this is all 2 digit rows
        two_to_three.append(i[0]+'0'+i[1])
    total_df_filter.loc[total_df_filter.seat_id.str.len()==2, 'seat_id'] = two_to_three

    three_to_four=[]
    for i in total_df_filter.loc[(total_df_filter.seat_id.str.len()==3) & (total_df_filter.seat_id.str[0]=='Z'), 'seat_id']: #3 digit with Z
        if(i[1].isalpha()==True):    # if second character is letter, such that last digit is defo single number ZA9
            three_to_four.append(i[0:2]+'0'+i[-1])  #E.g ZA+0+9
        else:
            three_to_four.append(i)  #append just in case E.G Z13 to ensure same df.loc length so can replace below
    total_df_filter.loc[(total_df_filter.seat_id.str.len()==3) & (total_df_filter.seat_id.str[0]=='Z'), 'seat_id']= three_to_four

    #Now sorting correctly!
    total_df_filter_2 = total_df_filter.sort_values(by=['Date','Time','seat_id','seat_block'], ascending=True)
    return total_df_filter_2

#Conditions for two consecutive seats in df to be adjacent, based on first and second seat_ids!
def condition(first,second):                                               #had ISSUE WITH B13 and B24  Note to self, BA3 would not exist, only after Z E.G ZA12
    
    if first[0]!=second[0]:                                                        #quickly removes U50 vs ZA2 etc
        condition=False
        
    elif len(first)==2:                                                            #E.G B1 vs B2....OR B9 vs B10
        condition=(   ((int(first[-1])+1) == int(second[-1]))   and   (first[0] == second[0])   )
        
    elif len(first)==3 and (first[-2].isalpha() == True):                          #E.G BA3 vs BA4  (middle letter)
        condition=(   ((int(first[-1])+1) == int(second[-1]))   and                #so test last number increase,
                    (first[-2] == second[-2]) and   (first[0] == second[0])   )    #and second/first character remaining!
        
    elif len(first)==3 and (first[-2].isalpha() == False):                         #E.G B13 vs B14  (middle number)
        condition=(   ((int(first[-2:])+1) == int(second[-2:]))   and              #so test last 2-dig no. increase,
                    (first[0] == second[0])   )                                    #and first character remaining!
        
    elif len(first)>2 and len(second)==2:
        condition=(   (int(first[-1])==0 and int(first[-2])==1 and int(second[-1])==9)   and 
                       (first[0] == second[0])   )                                           #E.G specific for B10 then B9

    else:  #E.G ZA10 vs ZA11....OR ZA10 vs ZB21
        condition=(   ((int(first[-2:])+1) == int(second[-2:]))   and              #so test last 2-dig no. increase,   
                    (first[-2] == second[-2]) and   (first[0] == second[0])   )    #and second/first character remaining!
            
    return condition

# Now checking whether seat conditions are True/False and assigning a number(n); making a function so can change Num
def adjacentseats(Num,df):                          #Num = number of seats E.G 2 for pair, 3 for three in a row
    n=0      # see later
    adj=[]   # to make df column of "n" after
    for i in range(len(df)-1):                      # for whole df, checking when condition is true
        A=df.iloc[i,1]
        B=df.iloc[i+1,1]
        if condition(A,B):
            #n=n+1
            n=1
        else:
            n=0
        adj.append(n)
    
    #Still need to add one more element to get correct length, last seat status!
    #FORTUNATELY should always be 0: If triplet, 1,1,0! If single, 0,0! If pair, 1,0! Last always 0! VERY IMPORTANT!
    adj.append(0)

    ## Now changing n numbers, to words/seat status
    adj2=[]
    i=0
    while i <= len(adj)-2:   #E.G for adj length 521, last term is index 520, so need stop at 519 so i+1=520
        if adj[i]==1 and adj[i+1]==0:    #If 1 followed by 0
            adj2.append('Pair')
            adj2.append('Pair')
            i=i+2
        elif adj[i]==0 and (adj[i+1]==1 or adj[i+1]==0):  #If 0 followed by 1
            adj2.append('Single')
            i=i+1
        elif adj[i]==1 and adj[i+1]==1:    #If 1 followed by 1...could be more 1s so need to check how many!
            j=2   #only for running loop, 2 so that adj[i+2] is the new one
            k=2   #for seeing how many seats adjacent to each other we have, starting on 2 as we already if ==1 twice (i,i+1)
            while j > 0 and (i+j)<=(len(adj)-1):  #to not check after last seat!
                if adj[i+j]==1:    #so if we have another 1 (i,i+1....i+j)
                    k=k+1          #we count it with k
                    j=j+1
                else:              #else we end the loop
                    j=0
                    
            for l in range(k+1):  #now appending correct amount of words
                adj2.append(f'{k+1}-in-a-row')   #so if we have a 1,1,0 (triplet) k=2, so need to use k+1=3
            i=i+k+1
            
        else:
            adj2.append(f'{adj[i]}-in-a-row')
            print('error?')
            i=i+1
            
    if len(adj2)==len(adj)-1:     #NOT SURE ABOUT THIS, assuming this solves issue only for final seat single?
        adj2.append('Single')
        
    df['Adjacent status']=adj2  #making new df column

    #Showing correct results, E.G Num=1 shows all seats...Num=2 shows pairs and up...etc! (can easily change to JUST pairs etc)
    if Num==0:
        print('No seats?')
        df2=pd.Dataframe() #empty
    elif Num==1:
        #df2 = df.loc[df['Adjacent status'].str.contains('Single')]              #Example of ^
        df2 = df
    elif Num==2:
        df2 = df.loc[~df['Adjacent status'].str.contains('Single')]   #Anything NOT single, for pairs and up
    else:
        df2=df.loc[~df['Adjacent status'].str.contains('Single') & ~df['Adjacent status'].str.contains('Pair')]   #remove special words
        if Num==3:
            pass  #as for Num=3, anything except singles and pairs, done already
        else:
            leftovers=np.arange(3,Num,1)  #E.G for Num=5, have already removed singles n pairs^, now need all but NOT 
                                          #3-in-row or 4-in-row. SO should be 3 to Num-1, but arange is non inclusive.
            
            for i in leftovers:                       #don't know how to loop with & so will instead remove ITERATIVELY!
                df2 = df2.loc[~df2['Adjacent status'].str.contains(f'{i}-in-a-row')]
        
    #display(df2)
    return(df2)

def compress(total_df_filter_3,total_df_cheapest):
    #total_df_compressed = total_df.groupby(['seat_id','seat_block']).agg(tuple).applymap(list).reset_index()
    total_df_compressed = total_df_filter_3.groupby(['seat_id','seat_block']).agg(tuple).applymap(list).reset_index()
    #total_df_compressed = total_df_filter_3.groupby(['Date','Time','seat_id','seat_block']).agg(tuple).applymap(list).reset_index()
    total_df_compressed['Seat_Code']=total_df_cheapest['level_1']
    total_df_compressed=total_df_compressed.set_index('Seat_Code').sort_index()
    #display(total_df_compressed)
    return(total_df_compressed)

def matching(chart_df,total_df_compressed):
    
    ordered_chart_df2=chart_df.sort_index().reset_index()
    ordered_chart_df2=ordered_chart_df2.set_index('level_1')

    combined=ordered_chart_df2.join(total_df_compressed)
    ordered_combined = combined.sort_values(by=['y','Seat_ID'], ascending=True)
    ordered_combined = ordered_combined.drop(['level_0','uuid','block_offset'],axis=1)

    ################################### PLOTTING see PLOTLY

    ordered_combined["colour"] = ordered_combined["legend"].str[0].fillna(0)  #making colour column
    #MAKE SURE TO CHANGE THESE TEST VALUES, NEAR PRICES SHOULD BE DIFF COLOURS
    colours=['gainsboro','#f95e5e','#ffa726','#fcabc7','#8febf7','#55cc5b','#ae87f2','#efdc32','#018930','#a37d70','gold','lime','#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd','#8c564b','#e377c2','#bcbd22','#17becf','darkorange','lightcoral','gold','paleturquoise','teal','violet','royalblue','blue','lime']
    colours1 = ordered_combined["legend"].str[0].unique()  #creating array of unique legend (first) values
    colours2 = np.nan_to_num(colours1)
    colours2.sort()

    for i in range(len(colours2)):
        ordered_combined["colour"]=ordered_combined["colour"].replace(colours2[i], f'{colours[i]}', regex=True)    

    #reducing some lists where E.G restricted view text has been repeated, to only one instance (as same seat has same issue)
    ordered_combined["is_restricted_view"] = ordered_combined["is_restricted_view"].str[0]
    ordered_combined["restricted_view_text"] = ordered_combined["restricted_view_text"].str[0]

    #display(ordered_combined)
    return(ordered_combined)


###################################################################################################################### PAGE DECO
######################################################################################################################

def set_bg_hack_url():
    st.markdown(
         f"""
         <style>
         .stApp {{
             background: url("https://upload.wikimedia.org/wikipedia/commons/3/37/Wicked_Map_%2821745639%29.jpeg");
             background-size: auto
         }}
         </style>
         """,
         unsafe_allow_html=True
     )
#set_bg_hack_url()

def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

local_css("style.css")

col1, col2 = st.columns(2)
###################################################################################################################### RUNNING THINGS
######################################################################################################################
tomorrow=datetime.date.today() + datetime.timedelta(days=1) #for starting values of input calendars

with col1:
    start_date = st.date_input(value=tomorrow, min_value=tomorrow, label="Start Date")      #input date 1
with col2:
    end_date = st.date_input(value=tomorrow, min_value=tomorrow, label="End Date")          #input date 2

number = st.number_input(min_value=1,max_value=50,step=1,label='Number of Seats')   #input no. seats

prices = st.slider(             #input prices
     'Price Range',
     0.0, 170.0, (25.0, 145.0))


if st.button('Find Seats'):
    
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))
    urls_load_state = st.text('Finding performance dates...')
    urls,all_perfs=PerfURLS(f'{start_date}',f'{end_date}')
    if urls==[]:                                                                     ## Error check
        st.error('No performances found within selected dates!')
        st.stop()
    urls_load_state.text("Performances found! (1/2) (without using st.cache)")
    
    driver = webdriver.Chrome(ChromeDriverManager().install())
    total_df_load_state = st.text('Finding seats...')
    total_df,total_df_cheapest = scrape_data(urls)
    driver.quit() #just incase, as cache is sometimes too fast!
    total_df_load_state.text("Seats found! (2/2) (without using st.cache)")
    
    total_df_filter=pricerange(f'{prices[0]}',f'{prices[1]}',total_df)
    if total_df_filter.empty:                                                        ## Error check
        st.error('No seats found within selected price range!')
        st.stop()
    total_df_filter_2 = correct_sort(total_df_filter)
    
    total_df_filter_3=adjacentseats(int(f'{number}'),total_df_filter_2)
    if total_df_filter_3.empty:                                                      ## Error check
        st.error("Cannot find "f'{number}'" seats together within given ranges!")
        st.stop()
    total_df_compressed=compress(total_df_filter_3,total_df_cheapest)
    
    chart_df=pd.read_csv('chart_data.csv',index_col=[0,1])
    text_df=pd.read_csv('text_data.csv',index_col=[0])
    
    ordered_combined=matching(chart_df,total_df_compressed)
    
else:
    st.write('Try it out!')
