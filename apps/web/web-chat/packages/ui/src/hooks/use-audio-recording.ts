import { useEffect, useRef, useState } from "react"

type RecordAudioType = {
    (stream: MediaStream): Promise<Blob>
    stop: () => void
    currentRecorder?: MediaRecorder
}

const recordAudio = (function (): RecordAudioType {
    const func = async function recordAudio(stream: MediaStream): Promise<Blob> {
        try {
            const mediaRecorder = new MediaRecorder(stream, {
                mimeType: "audio/webm;codecs=opus",
            })
            const audioChunks: Blob[] = []

            return new Promise((resolve, reject) => {
                mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0) {
                        audioChunks.push(event.data)
                    }
                }

                mediaRecorder.onstop = () => {
                    const audioBlob = new Blob(audioChunks, { type: "audio/webm" })
                    resolve(audioBlob)
                }

                mediaRecorder.onerror = () => {
                    reject(new Error("MediaRecorder error occurred"))
                }

                mediaRecorder.start(1000)
                    ; (func as RecordAudioType).currentRecorder = mediaRecorder
            })
        } catch (error) {
            const errorMessage =
                error instanceof Error ? error.message : "Unknown error occurred"
            throw new Error("Failed to start recording: " + errorMessage)
        }
    }

        ; (func as RecordAudioType).stop = () => {
            const recorder = (func as RecordAudioType).currentRecorder
            if (recorder && recorder.state !== "inactive") {
                recorder.stop()
            }
            delete (func as RecordAudioType).currentRecorder
        }

    return func as RecordAudioType
})()

interface UseAudioRecordingOptions {
    transcribeAudio?: (blob: Blob) => Promise<string>
    onTranscriptionComplete?: (text: string) => void
}

export function useAudioRecording({
    transcribeAudio,
    onTranscriptionComplete,
}: UseAudioRecordingOptions) {
    const [isListening, setIsListening] = useState(false)
    const [isSpeechSupported, setIsSpeechSupported] = useState(!!transcribeAudio)
    const [isRecording, setIsRecording] = useState(false)
    const [isTranscribing, setIsTranscribing] = useState(false)
    const [audioStream, setAudioStream] = useState<MediaStream | null>(null)
    const activeRecordingRef = useRef<Promise<Blob> | null>(null)

    useEffect(() => {
        const checkSpeechSupport = async () => {
            const hasMediaDevices = !!(
                navigator.mediaDevices && navigator.mediaDevices.getUserMedia
            )
            setIsSpeechSupported(hasMediaDevices && !!transcribeAudio)
        }

        checkSpeechSupport()
    }, [transcribeAudio])

    const stopRecording = async () => {
        setIsRecording(false)
        setIsTranscribing(true)
        try {
            recordAudio.stop()
            const recording = await activeRecordingRef.current
            if (transcribeAudio && recording) {
                const text = await transcribeAudio(recording)
                onTranscriptionComplete?.(text)
            }
        } catch (error) {
            console.error("Error transcribing audio:", error)
        } finally {
            setIsTranscribing(false)
            setIsListening(false)
            if (audioStream) {
                audioStream.getTracks().forEach((track) => track.stop())
                setAudioStream(null)
            }
            activeRecordingRef.current = null
        }
    }

    const toggleListening = async () => {
        if (!isListening) {
            try {
                setIsListening(true)
                setIsRecording(true)
                const stream = await navigator.mediaDevices.getUserMedia({
                    audio: true,
                })
                setAudioStream(stream)
                activeRecordingRef.current = recordAudio(stream)
            } catch (error) {
                console.error("Error recording audio:", error)
                setIsListening(false)
                setIsRecording(false)
                if (audioStream) {
                    audioStream.getTracks().forEach((track) => track.stop())
                    setAudioStream(null)
                }
            }
        } else {
            await stopRecording()
        }
    }

    return {
        isListening,
        isSpeechSupported,
        isRecording,
        isTranscribing,
        audioStream,
        toggleListening,
        stopRecording,
    }
}
