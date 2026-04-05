# Project - Live Translate
# ABSTRACT 
Language barriers are a major challenge in real-time communication, especially for regional language speakers and hearing-impaired individuals. The aim of the LIVE TRANSLATE project is to reduce these barriers by developing a platform that enables live translation during audio and video calls, similar to commonly used communication applications. The system focuses on converting live speech into text and audio in Malayalam, helping users who primarily understand regional languages. 

The platform takes live audio and video as input and processes them using speech recognition and translation techniques to provide real-time subtitles and translated audio output. One of the key features of the project is the integration of sign language translation, where gestures can be converted into text or speech and spoken or textual content can be converted into sign language. This ensures better accessibility for hearing-impaired users. 

Currently, there is no complete working platform that fully supports real-time communication for both regional language users and hearing-impaired individuals. Therefore, the scope of this project is high. The expected outcome is an inclusive and scalable communication system that can be applied in education, healthcare, public services, and everyday interactions.  

# PROBLEM DEFINITION 
Today, most communication happens through live audio and video calls using platforms like Google Meet, Zoom, or WhatsApp. While these platforms make communication faster, they do not fully solve the problem of language and accessibility barriers. People who speak regional languages such as Malayalam often struggle to understand conversations that take place in English or other widely used languages. Similarly, hearing-impaired individuals face difficulties because live calls mainly depend on spoken communication. 

Some existing platforms provide auto-captions or subtitles, but these features are usually limited to major languages and are not always accurate. Regional languages receive very little support, and even when subtitles are available, they may not work well in real time. In addition, sign language support is almost completely missing in live communication platforms. Current sign language tools usually work as separate applications and are not connected to video calls, making communication slow and inconvenient. 

The motivation behind the LIVE TRANSLATE project comes from this gap. There is no single platform that combines live video calls, regional language translation, and sign language support in one place. This project aims to bring all these features together, making live communication more inclusive, easier to understand, and accessible to everyone, including regional language users and hearing-impaired individual  

# TOOLS AND TECHNOLOGIES 

| Category	|	Tool / Technology 	|	Description |
| :------------ | :-----------| :---------- |
| Programming   	|	Python 			| Used for implementing client-side application logic, real-time communication handling, and interactive user interface behavior. |
| Libraries / 		 | React.js		|	A JavaScript library used to develop a modular, component-based web user interface with efficient state management. |
| Libraries / Frameworks | Flutter (Optional) | A cross-platform UI framework used to build mobile applications from a single codebase. 
| Libraries / Frameworks | React Native (Optional) | Used for developing native mobile applications using JavaScript and React principles. 
| Algorithms | Real-Time Streaming and Synchronization Algorithms | Ensure low-latency transmission and synchronization of audio, video, and subtitle streams during live communication. 
| Algorithms | Subtitle Rendering and Overlay Logic | Used to accurately render and align Malayalam subtitles over live video streams in real time. 
| APIs / Communication Protocols | WebRTC | Provides real-time peer-to-peer audio and video communication capabilities with minimal latency. 
| APIs / Communication Protocols | WebSocket / Socket.IO | Enables persistent, bidirectional communication for transmitting live subtitle text and synchronization data. 
| Backend / Communication Layer | WebRTC Signaling Server | Manages session initiation, peer discovery, and connection negotiation for real-time media streams. 
| Backend / Communication Layer | Socket.IO Server | Handles real-time subtitle updates and event-driven communication between system components. 
| User Interface Technologies | HTML5 Canvas | Used to dynamically render subtitle text and graphical overlays on video streams. 
| User Interface Technologies | Overlay Text Container | Provides a dedicated UI layer for displaying Malayalam subtitles in real time. 
| IDE | Visual Studio Code | Used for development, debugging, and maintenance of the project source code. 
| Version Control | GitHub | Used for source code management, version tracking, and collaborative development. 

# References
The below references are different from the original proposed papers: 
1. [L. Diduch, A. Fillinger, I. Hamchi, M. Hoarau, V. Stanford --
"SYNCHRONIZATION OF DATA STREAMS IN DISTRIBUTED REALTIME MULTIMODAL SIGNAL PROCESSING ENVIRONMENTS USING COMMODITY HARDWARE"](https://www.nist.gov/system/files/documents/itl/iad/mig/smartspace/ICME08_paper.pdf) 
2. ["NIST Data Flow System II - User's Guide - Draft Version - Chapter 5"](https://www.nist.gov/itl/iad/mig/nist-smart-space-project/nist-smart-space-project-data-flow/nist-data-flow-system-ii-4)
