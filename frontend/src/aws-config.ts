import { Amplify } from 'aws-amplify'

Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: 'ap-southeast-1_np4A4xyfA',
      userPoolClientId: '69lsr7uqfdagtp83v8n3h57gmk',
      loginWith: {
        username: true,
        email: false,
      },
    },
  },
})
