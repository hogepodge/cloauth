(ns cloauth.common
  (use clojure.math.numeric-tower))

(def rng (java.util.Random.))

(defn current-timestamp
  "Get the current timestamp in seconds since January 1, 1970 00:00:00 GMT, as an integer."
  []
  (quot (.getTime (java.util.Date.)) 1000))

(defn encode-base64
  "Encode the array of bytes in Base64"
  [databytes]
  (org.apache.commons.codec.binary.Base64/encodeBase64String databytes))

(defn sha1
    "Using the secret key encode the text using the SHA-1 algorithm"
    [secret text]
    (let [algorithm "HmacSHA1" 
          encoding "UTF-8" 
          signing-key (javax.crypto.spec.SecretKeySpec. (.getBytes secret encoding) algorithm) 
          mac (doto (javax.crypto.Mac/getInstance algorithm) (.init signing-key)) 
          raw-hmac (.doFinal mac (.getBytes text encoding))] 
      (.trim (encode-base64 raw-hmac))))

(defn generate-nonce
  [credentials]
  (str (- (current-timestamp) (:issue-time credentials)) ":" (abs (.nextInt rng))))

(defn generate-credentials
  []
  {:mac-key-identifier (str (java.util.UUID/randomUUID))
   :mac-key (str (java.util.UUID/randomUUID))
   :mac-algorithm "hmac-sha-1"
   :issue-time (current-timestamp)})

(defn normalize-request
  [nonce method uri hostname port bodyhash ext]
  (let [bodyhash (if (not bodyhash) "" bodyhash)] 
      (apply str (interpose "\n" [nonce 
                                  (.toUpperCase method) 
                                  uri 
                                  (.toLowerCase hostname) 
                                  port bodyhash ext ""]))))

(defn encode-mac-authorization
  [credentials nonce signature bodyhash ext]
  (str "MAC id=\"" (:mac-key-identifier credentials)
       "\", nonce=\"" nonce
       "\", bodyhash=\"" bodyhash
       "\", ext=\"" ext 
       "\", mac=\"" signature "\""))


(comment 
(println (current-timestamp))
(println (generate-credentials))
(def creds (generate-credentials))
(print creds)
(Thread/sleep 3000)
(println (generate-nonce creds))
(def norm1 (normalize-request 
           "264095:7d8f3e4a"
           "post"
           "/request?b5=%3D%253D&a3=a&c%40=&a2=r%20b&c2&a3=2+q"
           "EXAMPLE.COM"
           80
           "Lve90gjOVATpfV8EL5X4nxwjKHE="
           "a,b,c"))
(println norm1)

(def norm2 (normalize-request 
           "264095:dj83hs9s"
           "get"
           "/resource/1?b=1&a=2"
           "EXAMPLE.COM"
           80
           ""
           ""))
(println norm2)
(println (sha1 "489dks293j39" norm2))
)
