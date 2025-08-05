# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.0] - 2025-08-05

### Added

- **HLG Transfer Characteristics Preservation**: Enhanced video muxing to preserve HLG color metadata
  - Added automatic detection of HLG video tracks during muxing process
  - Implemented `--color-transfer-characteristics 0:18` argument for mkvmerge when processing HLG content
  - Prevents incorrect conversion from HLG (18) to BT.2020 (14) transfer characteristics
  - Ensures proper HLG playback support on compatible hardware without manual editing
- **Original Language Support**: Enhanced language selection with 'orig' keyword support
  - Added support for 'orig' language selector for both video and audio tracks
  - Automatically detects and uses the title's original language when 'orig' is specified
  - Improved language processing logic with better duplicate handling
  - Enhanced help text to document original language selection usage
- **Forced Subtitle Support**: Added option to include forced subtitle tracks
  - New functionality to download and include forced subtitle tracks alongside regular subtitles
- **WebVTT Subtitle Filtering**: Enhanced subtitle processing capabilities
  - Added filtering for unwanted cues in WebVTT subtitles
  - Improved subtitle quality by removing unnecessary metadata

### Changed

- **DRM Track Decryption**: Improved DRM decryption track selection logic
  - Enhanced `get_drm_for_cdm()` method usage for better DRM-CDM matching
  - Added warning messages when no matching DRM is found for tracks
  - Improved error handling and logging for DRM decryption failures
- **Series Tree Representation**: Enhanced episode tree display formatting
  - Updated series tree to show season breakdown with episode counts
  - Improved visual representation with "S{season}({count})" format
  - Better organization of series information in console output
- **Hybrid Processing UI**: Enhanced extraction and conversion processes
  - Added dynamic spinning bars to follow the rest of the codebase design
  - Improved visual feedback during hybrid HDR processing operations
- **Track Selection Logic**: Enhanced multi-track selection capabilities
  - Fixed track selection to support combining -V, -A, -S flags properly
  - Improved flexibility in selecting multiple track types simultaneously
- **Service Subtitle Support**: Added configuration for services without subtitle support
  - Services can now indicate if they don't support subtitle downloads
  - Prevents unnecessary subtitle download attempts for unsupported services
- **Update Checker**: Enhanced update checking logic and cache handling
  - Improved rate limiting and caching mechanisms for update checks
  - Better performance and reduced API calls to GitHub

### Fixed

- **PlayReady KID Extraction**: Enhanced KID extraction from PSSH data
  - Added base64 support and XML parsing for better KID detection
  - Fixed issue where only one KID was being extracted for certain services
  - Improved multi-KID support for PlayReady protected content
- **Dolby Vision Detection**: Improved DV codec detection across all formats
  - Fixed detection of dvhe.05.06 codec which was not being recognized correctly
  - Enhanced detection logic in Episode and Movie title classes
  - Better support for various Dolby Vision codec variants

## [1.3.0] - 2025-08-03

### Added

- **mp4decrypt Support**: Alternative DRM decryption method using mp4decrypt from Bento4
  - Added `mp4decrypt` binary detection and support in binaries module
  - New `decryption` configuration option in unshackle.yaml for service-specific decryption methods
  - Enhanced PlayReady and Widevine DRM classes with mp4decrypt decryption support
  - Service-specific decryption mapping allows choosing between `shaka` and `mp4decrypt` per service
  - Improved error handling and progress reporting for mp4decrypt operations
- **Scene Naming Configuration**: New `scene_naming` option for controlling file naming conventions
  - Added scene naming logic to movie, episode, and song title classes
  - Configurable through unshackle.yaml to enable/disable scene naming standards
- **Terminal Cleanup and Signal Handling**: Enhanced console management
  - Implemented proper terminal cleanup on application exit
  - Added signal handling for graceful shutdown in ComfyConsole
- **Configuration Template**: New `unshackle-example.yaml` template file
  - Replaced main `unshackle.yaml` with example template to prevent git conflicts
  - Users can now modify their local config without affecting repository updates
- **Enhanced Credential Management**: Improved CDM and vault configuration
  - Expanded credential management documentation in configuration
  - Enhanced CDM configuration examples and guidelines
- **Video Transfer Standards**: Added `Unspecified_Image` option to Transfer enum
  - Implements ITU-T H.Sup19 standard value 2 for image characteristics
  - Supports still image coding systems and unknown transfer characteristics
- **Update Check Rate Limiting**: Enhanced update checking system
  - Added configurable update check intervals to prevent excessive API calls
  - Improved rate limiting for GitHub API requests

### Changed

- **DRM Decryption Architecture**: Enhanced decryption system with dual method support
  - Updated `dl.py` to handle service-specific decryption method selection
  - Refactored `Config` class to manage decryption method mapping per service
  - Enhanced DRM decrypt methods with `use_mp4decrypt` parameter for method selection
- **Error Handling**: Improved exception handling in Hybrid class
  - Replaced log.exit calls with ValueError exceptions for better error propagation
  - Enhanced error handling consistency across hybrid processing

### Fixed

- **Proxy Configuration**: Fixed proxy server mapping in configuration
  - Renamed 'servers' to 'server_map' in proxy configuration to resolve Nord/Surfshark naming conflicts
  - Updated configuration structure for better compatibility with proxy providers
- **HTTP Vault**: Improved URL handling and key retrieval logic
  - Fixed URL processing issues in HTTP-based key vaults
  - Enhanced key retrieval reliability and error handling

## [1.2.0] - 2025-07-30

### Added

- **Update Checker**: Automatic GitHub release version checking on startup
  - Configurable update notifications via `update_checks` setting in unshackle.yaml
  - Non-blocking HTTP requests with 5-second timeout for performance
  - Smart semantic version comparison supporting all version formats (x.y.z, x.y, x)
  - Graceful error handling for network issues and API failures
  - User-friendly update notifications with current → latest version display
  - Direct links to GitHub releases page for easy updates
- **HDR10+ Support**: Enhanced HDR10+ metadata processing for hybrid tracks
  - HDR10+ tool binary support (`hdr10plus_tool`) added to binaries module
  - HDR10+ to Dolby Vision conversion capabilities in hybrid processing
  - Enhanced metadata extraction for HDR10+ content
- **Duration Fix Handling**: Added duration correction for video and hybrid tracks
- **Temporary Directory Management**: Automatic creation of temp directories for attachment downloads

### Changed

- Enhanced configuration system with new `update_checks` boolean option (defaults to true)
- Updated sample unshackle.yaml with update checker configuration documentation
- Improved console styling consistency using `bright_black` for dimmed text
- **Environment Dependency Check**: Complete overhaul with detailed categorization and status summary
  - Organized dependencies by category (Core, HDR, Download, Subtitle, Player, Network)
  - Enhanced status reporting with compact summary display
  - Improved tool requirement tracking and missing dependency alerts
- **Hybrid Track Processing**: Significant improvements to HDR10+ and Dolby Vision handling
  - Enhanced metadata extraction and processing workflows
  - Better integration with HDR processing tools

### Removed

- **Docker Workflow**: Removed Docker build and publish GitHub Actions workflow for manual builds

## [1.1.0] - 2025-07-29

### Added

- **HDR10+DV Hybrid Processing**: New `-r HYBRID` command for processing HDR10 and Dolby Vision tracks
  - Support for hybrid HDR processing and injection using dovi_tool
  - New hybrid track processing module for seamless HDR10/DV conversion
  - Automatic detection and handling of HDR10 and DV metadata
- Support for HDR10 and DV tracks in hybrid mode for EXAMPLE service
- Binary availability check for dovi_tool in hybrid mode operations
- Enhanced track processing capabilities for HDR content

### Fixed

- Import order issues and missing json import in hybrid processing
- UV installation process and error handling improvements
- Binary search functionality updated to use `binaries.find`

### Changed

- Updated package version from 1.0.2 to 1.1.0
- Enhanced dl.py command processing for hybrid mode support
- Improved core titles (episode/movie) processing for HDR content
- Extended tracks module with hybrid processing capabilities
