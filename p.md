# Configuring Single Sign-On (SSO) in BioStar 2

To configure Single Sign-On (SSO) in BioStar 2 and improve login convenience, follow these steps based on the relevant documentation:

## 1. Ensure You Have the Correct Version and License

- The SSO feature requires that your BioStar 2 version is at least 2.8.16 or higher[1].
- Ensure that you possess an active BioStar 2 AC license, which is necessary for using Advanced features, including SSO[2].

## 2. Configure Active Directory Integration

- Go to **Settings > Active Directory > Active Directory Server** in the BioStar 2 interface to begin the configuration[1].
- Fill in the **Active Directory Server** details, such as the server address and connection settings. You can test the connection using the "Test Connect" option[4][5].

## 3. Enable BioStar 2 Login with Active Directory

- You need to enable the option labeled "Use for BioStar 2 Login" within the Active Directory settings[1][2].

## 4. Testing the Configuration

- After completing the configuration steps, test your setup by attempting to log into BioStar 2 using an Active Directory account. The system should verify the credentials against the Active Directory server[1][4].

## 5. Using APIs for SSO

- If you need to implement SSO programmatically, you can utilize the BioStar 2 API. Specifically, use the endpoint `POST /login/sso` after acquiring the proper session ID from `/api/login`. Follow detailed API documentation on how to obtain the session ID[10].

## 6. Documentation References

- For detailed instructions on how to set up Active Directory Integration, refer to the document titled "How To Configure Active Directory in BioStar2" which is available [here](https://support.supremainc.com/en/support/solutions/articles/24000044140)[11].
- To confirm Active Directory information pertinent to your system configuration, use the guide [How To Confirm Active Directory Information](https://support.supremainc.com/en/support/solutions/articles/24000041940)[1].

Following these steps will help you successfully implement Single Sign-On in BioStar 2 using Active Directory, improving overall login convenience for your users. If you encounter any issues, consider reaching out to Suprema support or consult the comprehensive documentation provided.