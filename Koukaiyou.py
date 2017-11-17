# -*- coding: utf-8 -*-
 
from requests_oauthlib import OAuth1Session
import json
import datetime, time, sys
from abc import ABCMeta, abstractmethod

import numpy as np
 

#ここにTwitterのキーを入力
CK = ''                             # Consumer Key
CS = ''    # Consumer Secret
AT = ''    # Access Token
AS = ''         # Accesss Token Secert
 
class TweetsGetter(object):
    __metaclass__ = ABCMeta
 
    def __init__(self):
        self.session = OAuth1Session(CK, CS, AT, AS)
 
    @abstractmethod
    def specifyUrlAndParams(self, keyword):
        '''
        呼出し先 URL、パラメータを返す
        '''
 
    @abstractmethod
    def pickupTweet(self, res_text, includeRetweet):
        '''
        res_text からツイートを取り出し、配列にセットして返却
        '''

    @abstractmethod
    def getLimitContext(self, res_text):
        '''
        回数制限の情報を取得 （起動時）
        '''
 
    def collect(self, total = -1, onlyText = False, includeRetweet = False):
        '''
        ツイート取得を開始する
        '''
 
        #----------------
        # 回数制限を確認
        #----------------
        self.checkLimit()
 
        #----------------
        # URL、パラメータ
        #----------------
        url, params = self.specifyUrlAndParams()
        params['include_rts'] = str(includeRetweet).lower()
        # include_rts は statuses/user_timeline のパラメータ。search/tweets には無効
 
        #----------------
        # ツイート取得
        #----------------
        cnt = 0
        unavailableCnt = 0
        while True:
            res = self.session.get(url, params = params)
            if res.status_code == 503:
                # 503 : Service Unavailable
                if unavailableCnt > 10:
                    raise Exception('Twitter API error %d' % res.status_code)
 
                unavailableCnt += 1
                print ('Service Unavailable 503')
                self.waitUntilReset(time.mktime(datetime.datetime.now().timetuple()) + 30)
                continue
 
            unavailableCnt = 0
 
            if res.status_code != 200:
                raise Exception('Twitter API error %d' % res.status_code)
 
            tweets = self.pickupTweet(json.loads(res.text))
            if len(tweets) == 0:
                # len(tweets) != params['count'] としたいが
                # count は最大値らしいので判定に使えない。
                # ⇒  "== 0" にする
                # https://dev.twitter.com/discussions/7513
                break
 
            for tweet in tweets:
                if (('retweeted_status' in tweet) and (includeRetweet is False)):
                    pass
                else:
                    if onlyText is True:
                        yield tweet['text']
                    else:
                        yield tweet
 
                    cnt += 1
                    #ツイート取得した回数を表示
                    # if cnt % 100 == 0:
                    #     print ('%d件 ' % cnt)
 
                    if total > 0 and cnt >= total:
                        return
 
            params['max_id'] = tweet['id'] - 1
 
            # ヘッダ確認 （回数制限）
            # X-Rate-Limit-Remaining が入ってないことが稀にあるのでチェック
            if ('X-Rate-Limit-Remaining' in res.headers and 'X-Rate-Limit-Reset' in res.headers):
                if (int(res.headers['X-Rate-Limit-Remaining']) == 0):
                    self.waitUntilReset(int(res.headers['X-Rate-Limit-Reset']))
                    self.checkLimit()
            else:
                print ('not found  -  X-Rate-Limit-Remaining or X-Rate-Limit-Reset')
                self.checkLimit()
 
    def checkLimit(self):
        '''
        回数制限を問合せ、アクセス可能になるまで wait する
        '''
        unavailableCnt = 0
        while True:
            url = "https://api.twitter.com/1.1/application/rate_limit_status.json"
            res = self.session.get(url)
 
            if res.status_code == 503:
                # 503 : Service Unavailable
                if unavailableCnt > 10:
                    raise Exception('Twitter API error %d' % res.status_code)
 
                unavailableCnt += 1
                print ('Service Unavailable 503')
                self.waitUntilReset(time.mktime(datetime.datetime.now().timetuple()) + 30)
                continue
 
            unavailableCnt = 0
 
            if res.status_code != 200:
                raise Exception('Twitter API error %d' % res.status_code)
 
            remaining, reset = self.getLimitContext(json.loads(res.text))
            if (remaining == 0):
                self.waitUntilReset(reset)
            else:
                break
 
    def waitUntilReset(self, reset):
        '''
        reset 時刻まで sleep
        '''
        seconds = reset - time.mktime(datetime.datetime.now().timetuple())
        seconds = max(seconds, 0)
        print ('\n     =====================')
        print ('     == waiting %d sec ==' % seconds)
        print ('     =====================')
        sys.stdout.flush()
        time.sleep(seconds + 10)  # 念のため + 10 秒
 
    @staticmethod
    def bySearch(keyword):
        return TweetsGetterBySearch(keyword)
 
    @staticmethod
    def byUser(screen_name):
        return TweetsGetterByUser(screen_name)
 
 
class TweetsGetterBySearch(TweetsGetter):
    '''
    キーワードでツイートを検索
    '''
    def __init__(self, keyword):
        super(TweetsGetterBySearch, self).__init__()
        self.keyword = keyword
        
    def specifyUrlAndParams(self):
        '''
        呼出し先 URL、パラメータを返す
        '''
        url = 'https://api.twitter.com/1.1/search/tweets.json'
        params = {'q':self.keyword, 'count':100}
        return url, params
 
    def pickupTweet(self, res_text):
        '''
        res_text からツイートを取り出し、配列にセットして返却
        '''
        results = []
        for tweet in res_text['statuses']:
            results.append(tweet)
 
        return results
 
    def getLimitContext(self, res_text):
        '''
        回数制限の情報を取得 （起動時）
        '''
        remaining = res_text['resources']['search']['/search/tweets']['remaining']
        reset     = res_text['resources']['search']['/search/tweets']['reset']
 
        return int(remaining), int(reset)
    
 
class TweetsGetterByUser(TweetsGetter):
    '''
    ユーザーを指定してツイートを取得
    '''
    def __init__(self, screen_name):
        super(TweetsGetterByUser, self).__init__()
        self.screen_name = screen_name
        
    def specifyUrlAndParams(self):
        '''
        呼出し先 URL、パラメータを返す
        '''
        url = 'https://api.twitter.com/1.1/statuses/user_timeline.json'
        params = {'screen_name':self.screen_name, 'count':200}
        return url, params
 
    def pickupTweet(self, res_text):
        '''
        res_text からツイートを取り出し、配列にセットして返却
        '''
        results = []
        for tweet in res_text:
            results.append(tweet)
 
        return results
 
    def getLimitContext(self, res_text):
        '''
        回数制限の情報を取得 （起動時）
        '''
        remaining = res_text['resources']['statuses']['/statuses/user_timeline']['remaining']
        reset     = res_text['resources']['statuses']['/statuses/user_timeline']['reset']
 
        return int(remaining), int(reset)
 
 
if __name__ == '__main__':
    name = np.array([""]) #ここにIDを@なしで入れる

    for index in range(name.shape[0]):
        # キーワードで取得
        # getter = TweetsGetter.bySearch(u'＃コンテンツ応用論2017')
    
        # ユーザーを指定して取得 （screen_name）
        getter = TweetsGetter.byUser(name[index])
        TweetNum = 0 #タグ付きツイートした回数
        cnt = 0
        total = 500 #検索するツイート数
        date = 0 #この変数に一番最初にタグ付きツイートした日を入れる
        attend = np.zeros(6) # 出席したか否かを格納する配列　配列の順に授業日が入る

        for tweet in getter.collect(total):
            # ここら辺を実行するとツイート内容がひたすら表示される
            # cnt += 1
            # print(tweet['user']['screen_name'])
            # print ('------ %d' % cnt)
            # print ('{} {} {}'.format(tweet['id'], tweet['created_at'], '@'+tweet['user']['screen_name']))
            # print (tweet['text'])

            
            #コンテンツ応用論の回数をカウント
            if "#コンテンツ応用論2017" in tweet['text']:
                TweetNum += 1

                #Twitter APIの日付情報を比較できる形に変換
                date = tweet['created_at']
                timearr = date.split(" ")
                if "Jan" in timearr[1]:
                    timearray[1] = "01"
                elif "Feb" in timearr[1]:
                    timearr[1] = "02"
                elif "Mar" in timearr[1]:
                        timearr[1] = "03"
                elif "Apr" in timearr[1]:
                    timearr[1] = "04"
                elif "May" in timearr[1]:
                    timearr[1] = "05"
                elif "Jun" in timearr[1]:
                    timearr[1] = "06"
                elif "Jul" in timearr[1]:
                    timearr[1] = "07"
                elif "Aug" in timearr[1]:
                    timearr[1] = "08"
                elif "Sep" in timearr[1]:
                    timearr[1] = "09"
                elif "Oct" in timearr[1]:
                     timearr[1] = "10"
                elif "Nov" in timearr[1]:
                    timearr[1] = "11"
                else:
                    timearr[1] = "12"
                tw_time = ('{}{}{}{}'.format(timearr[5], "-" + timearr[1], "-" + timearr[2], " " + timearr[3])) #比較できる形に変換されたツイート時刻

                # ツイートのタイミングに応じて出席を記録
                if (tw_time > "2017-10-02 15:00:00" and tw_time < "2017-10-10 15:00:00"):
                    attend[0] += 1
                elif (tw_time > "2017-10-10 15:00:00" and tw_time < "2017-10-16 15:00:00"):
                    attend[1] += 1
                elif (tw_time > "2017-10-16 15:00:00" and tw_time < "2017-10-23 15:00:00"):
                    attend[2] += 1
                elif (tw_time > "2017-10-23 15:00:00" and tw_time < "2017-10-30 15:00:00"):
                    attend[3] += 1
                elif (tw_time > "2017-10-30 15:00:00" and tw_time < "2017-11-13 15:00:00"):
                    attend[4] += 1
                elif (tw_time > "2017-11-13 15:00:00" and tw_time < "2017-11-20 15:00:00"):
                    attend[5] += 1
                else:
                    pass

        #ツイートした回数を表示
        print (name[index], end = "")
        print ('さんの第2回からの#コンテンツ応用論2017のタグ付きツイート回数は 第2回{0[0]}, 第3回 {0[1]}, 第4回 {0[2]}, 第5回 {0[3]}, 第6回 {0[4]}'.format(attend))