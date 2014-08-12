(ns cloauth.client
  (use cloauth.common)
  (require [clj-http.client :as client]))

(defn wrap-oauth-client [fxn credentials]
  (fn [request]
    (let [nonce (generate-nonce credentials)
          method (if (:method request) (name (:method request)) "GET")
          {uri :uri
           hostname :server-name
           port :server-port} (client/parse-url (:url request))
          body (if (:body request) (:body request) "")
          bodyhash (sha1 (:mac-key credentials) body) 
          ext (:ext request)
          normalization (normalize-request nonce method uri hostname port bodyhash ext)
          signature (sha1 (:mac-key credentials) normalization)
          authorization (encode-mac-authorization credentials nonce signature bodyhash ext)
          updated-request (assoc-in request [:headers "Authorization"] authorization)]
      (println updated-request)
      (fxn updated-request))))


(comment
(def credentials {:mac-key-identifier "6042330f-d018-4b71-bd48-a28d1a268d7f", 
                 :mac-key "cdc12e4f-92c0-4a0a-bdc3-f4100d879510", 
                 :mac-algorithm "hmac-sha-1", 
                 :issue-time 1319826217})

(def oauth-request (wrap-oauth-client client/request credentials))
)
(println (sha1 "8yfrufh348h" "hello=world%21"))


(println (sha1 "cdc12e4f-92c0-4a0a-bdc3-f4100d879510" "433002:425827369885\nGET\n/mri?xml=\nlocalhost\n80\n0c6x6df2H6xBUsRdMJayCwbGd7s=\n\n"))
(comment
(println (oauth-request {:url 
;                         "http://localhost:3604/mri?xml="
                         "http://localhost:3604/mri/id/298"
                :method :get}))
)
(comment

(def credentials-notexist {:mac-key-identifier "6042330f-d018-4b71-bd48-a28d1a268d7f ", 
                 :mac-key "cdc12e4f-92c0-4a0a-bdc3-f4100d879510", 
                 :mac-algorithm "hmac-sha-1", 
                 :issue-time 1319826217})

(def credentials-badkey {:mac-key-identifier "6042330f-d018-4b71-bd48-a28d1a268d7f", 
                 :mac-key "cdc12e4f-92c0-4a0a-bdc3-f4100d879510 ", 
                 :mac-algorithm "hmac-sha-1", 
                 :issue-time 1319826217})

(def oauth-request (wrap-oauth-client client/request credentials))
(def oauth-request-bad (wrap-oauth-client client/request credentials-badkey))

  (println (oauth-request {:url "http://localhost:5555/test" :method :get}))
  (println (oauth-request-bad {:url "http://localhost:5555/test" :method :get}))
)
