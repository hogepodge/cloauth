(ns cloauth.server
  (use cloauth.common)
  (use compojure.core)
;  (use compojure.route)
  (use ring.adapter.jetty)
  (use ring.util.response))

(defn oauth-fail
  "The oauth request failed with an error."
  [request handler error]
  (handler (assoc request :oauth-ok false :oauth-error error)))

(defn oauth-success
  "The oauth request was successful."
  [request handler username]
  (handler (assoc request :oauth-ok true :oauth-user username)))

(defn oauth-not-used
  "Oauth was not used, so oauth-ok is false with no oauth-error message."
  [request handler]
  (handler (assoc request :oauth-ok false)))

(defn nonce!?
  "Checks if a nonce has been used. If not, add it to the used nonce store and return true."
  [nonce store]
  (if nonce (dosync
          (if (not (store nonce))
            (do (alter store assoc nonce (current-timestamp))
              (println store)
              true)
            false))))

(defn slurp-body!
  "Read the request body and replace the input stream with a new byte stream to be reread
  downstream by other methods. Mutates content of request."
  [request]
  (let [body (:body request)]
    request))
;    (if body
;      (do (println body)
;      (let [body (slurp body)]
;        (assoc request
;               :body (java.io.ByteArrayInputStream. (.getBytes body))
;               :body-string body)))
;      request)))


(defn decode-authorization-value
  "Decode a key-value string of the form key=\"value\" with k being a symbol for the value.
  i.e. nonce=\"123456\" can be decoded with the k value :nonce"
  [auth k]
  (let [pattern (java.util.regex.Pattern/compile (str "\\b(?i:" (name k) ")=\"(.*?)\""))
        match (re-seq pattern auth)]
    (second (first match))))

(defn decode-mac-authorization
  "Decode the MAC authorization header and place the values into a map"
  [auth]
  (let [auth (if auth (.trim auth) "")]
    (if (.startsWith auth "MAC")
      (into {:oauth true }
            (map #(vector % (decode-authorization-value auth %))
                 [:id :nonce :bodyhash :ext :mac]))
      {:oauth false })))


(defn extract-attributes
  [request]
  (let [auth (decode-mac-authorization ((:headers request) "authorization"))]
    {:scheme (name (request :scheme))
     :server-name (request :server-name) 
     :server-port (request :server-port) 
     :uri (request :uri)
     :oauth (:oauth auth)
     :id (:id auth)
     :nonce (:nonce auth)
     :bodyhash (:bodyhash auth)
     :ext (:ext auth)
     :mac (:mac auth)}))

(defn check-bodyhash!
  "Check the bodyhash on the request. Mutates request"
  [request attributes credentials]
  (let [request (slurp-body! request)
        body (request :body-string)
        bodyhash (sha1 (:mac-key credentials) body)
        request (assoc-in request [:oauth-verify :bodyhash] (= bodyhash (:bodyhash attributes)))]
    (println (str "computed: " bodyhash
                  "sent:     " (:bodyhash attributes)
                  (= bodyhash (:bodyhash attributes))
                  (count bodyhash) " " (count (:bodyhash attributes))))
    request))

(defn check-nonce!
  "Check the nonce on the request. Mutates the nonce store"
  [request attributes credentials store]
  (assoc-in request [:oauth-verify :nonce] (nonce!? (:nonce attributes) store)))

(defn check-mac
  [request attributes credentials]
  (let [querystring (:query-string request)
        uri (:uri request)
        uri (if querystring (str uri "?" querystring) uri)
        normalization (normalize-request (:nonce attributes) 
                                         (name (:request-method request))
                                         uri
                                         (:server-name request)
                                         (:server-port request)
                                         (:bodyhash attributes)
                                         (:ext attributes))
        mac (sha1 (:mac-key credentials) normalization)]
    (assoc-in request [:oauth-verify :mac] (= mac (:mac attributes)))))

(defn wrap-oauth
  [handler token-store nonce-store check-bodyhash?]
  (fn [request]
    (let [attributes (extract-attributes request)
          credentials (token-store (attributes :id))]
      (if (:oauth attributes)
        (if credentials 
          (do 
            (println credentials)
            (let [request (if check-bodyhash? (check-bodyhash! request attributes credentials) (slurp-body! request))
                  request (check-nonce! request attributes credentials nonce-store)
                  request (check-mac request attributes credentials)] 
              (if (and check-bodyhash? (not (:bodyhash (:oauth-verify request))))
                (oauth-fail request handler "Invalid bodyhash")
                (if (not (:nonce (:oauth-verify request)))
                  (oauth-fail request handler "Invalid nonce")
                  (if (not (:mac (:oauth-verify request)))
                    (oauth-fail request handler "Invalid signature")
                    (oauth-success request handler (:user-name credentials)))))))
          (oauth-fail request handler "Invalid OAuth token"))
        (oauth-not-used request handler)))))

(comment 
(defroutes oauth-test
  (ANY "/test" params #(do (println params) (str "default" %)))
  (ANY "*" params #(do (println params) ("none"))))


(def tokens { "6042330f-d018-4b71-bd48-a28d1a268d7f" {:mac-key-identifier "6042330f-d018-4b71-bd48-a28d1a268d7f", 
                                                     :mac-key "cdc12e4f-92c0-4a0a-bdc3-f4100d879510", 
                                                     :mac-algorithm "hmac-sha-1", 
                                                     :issue-time 1319826217} })
             
(def nonce-store (ref {}))

;(wrap! oauth-test (:charset "utf8"))
(run-jetty (wrap-oauth oauth-test tokens nonce-store) {:port 5555})


(comment (println (decode-mac-authorization " MAC id=\"jd93dh9dh39D\",
                                   nonce=\"273156:di3hvdf8\",
                                   bodyhash=\"k9kbtCIy0CkI3/FEfpS/oIDjk6k=\",
                                   mac=\"W7bdMZbv9UWOTadASIQHagZyirA=\""))
)

)
